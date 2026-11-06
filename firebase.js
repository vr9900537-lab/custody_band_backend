// =====================================================================
// Complete Firebase Web SDK Integration for Custody Band
// Project: custody-band-a8f59 (Custody Band)
// =====================================================================

import { initializeApp, getApps, getApp } from "firebase/app";
import { getAnalytics, isSupported } from "firebase/analytics";
import {
  getFirestore,
  collection,
  doc,
  setDoc,
  addDoc,
  getDoc,
  getDocs,
  updateDoc,
  onSnapshot,
  query,
  orderBy,
  limit,
  where,
  serverTimestamp
} from "firebase/firestore";
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged
} from "firebase/auth";

// 1. Firebase Project Configuration
export const firebaseConfig = {
  apiKey: "AIzaSyDtJWj50jBIJfZSyEizZq-sw8bWIjUZlC8",
  authDomain: "custody-band-a8f59.firebaseapp.com",
  projectId: "custody-band-a8f59",
  storageBucket: "custody-band-a8f59.firebasestorage.app",
  messagingSenderId: "334876318466",
  appId: "1:334876318466:web:9de599fa07a040c8f1801b",
  measurementId: "G-3JHFFF76G9"
};

// 2. Initialize Firebase App (Singleton Pattern)
export const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();

// 3. Initialize Firebase Services
export const db = getFirestore(app);
export const auth = getAuth(app);

// 4. Safe Analytics Initialization for Browser
export let analytics = null;
if (typeof window !== "undefined") {
  isSupported().then((supported) => {
    if (supported) {
      analytics = getAnalytics(app);
      console.log("Firebase Analytics initialized successfully");
    }
  });
}

// =====================================================================
// FIRESTORE DATABASE METHODS
// =====================================================================

// --- DEVICES COLLECTION ---

/**
 * Save or update a custody watch in Firestore
 */
export async function saveDevice(deviceData) {
  const deviceId = String(deviceData.device_id || deviceData.id || deviceData.imei);
  const deviceRef = doc(db, "devices", deviceId);
  const payload = {
    ...deviceData,
    device_id: deviceId,
    updated_at: new Date().toISOString()
  };
  await setDoc(deviceRef, payload, { merge: true });
  return payload;
}

/**
 * Real-time listener for all monitored devices
 */
export function subscribeToDevices(onUpdate, onError) {
  const q = collection(db, "devices");
  return onSnapshot(q, (snapshot) => {
    const devices = snapshot.docs.map((docSnap) => ({
      id: docSnap.id,
      ...docSnap.data()
    }));
    onUpdate(devices);
  }, (err) => {
    console.error("Firestore devices subscription error:", err);
    if (onError) onError(err);
  });
}

/**
 * Fetch all registered devices once
 */
export async function getAllDevices() {
  const snapshot = await getDocs(collection(db, "devices"));
  return snapshot.docs.map((docSnap) => ({
    id: docSnap.id,
    ...docSnap.data()
  }));
}

// --- GPS TELEMETRY & BREADCRUMBS ---

/**
 * Ingest GPS telemetry coordinate fix into Firestore
 */
export async function saveTelemetry(telemetryData) {
  const deviceId = String(telemetryData.device_id || telemetryData.imei);
  const timestamp = telemetryData.timestamp || new Date().toISOString();

  const record = {
    ...telemetryData,
    device_id: deviceId,
    timestamp: timestamp
  };

  // 1. Add to global telemetry collection
  await addDoc(collection(db, "telemetry"), record);

  // 2. Add to device breadcrumbs subcollection
  await addDoc(collection(db, "devices", deviceId, "history"), record);

  // 3. Update device's latest position in device doc
  const deviceRef = doc(db, "devices", deviceId);
  await setDoc(deviceRef, {
    last_latitude: telemetryData.latitude,
    last_longitude: telemetryData.longitude,
    battery: telemetryData.battery,
    steps: telemetryData.steps,
    status: "ONLINE",
    last_seen: timestamp
  }, { merge: true });

  return record;
}

/**
 * Real-time listener for breadcrumb trail of a specific watch
 */
export function subscribeToDeviceHistory(deviceId, onUpdate, maxLimit = 100) {
  const q = query(
    collection(db, "devices", deviceId, "history"),
    orderBy("timestamp", "desc"),
    limit(maxLimit)
  );
  return onSnapshot(q, (snapshot) => {
    const history = snapshot.docs.map((docSnap) => ({
      id: docSnap.id,
      ...docSnap.data()
    }));
    onUpdate(history);
  });
}

// --- ALERTS COLLECTION ---

/**
 * Save a security alert (tamper, SOS, low battery, geofence)
 */
export async function saveAlert(alertData) {
  const alertPayload = {
    ...alertData,
    timestamp: alertData.timestamp || new Date().toISOString(),
    status: alertData.status || "NEW"
  };
  const docRef = await addDoc(collection(db, "alerts"), alertPayload);
  return { id: docRef.id, ...alertPayload };
}

/**
 * Real-time listener for security alerts feed
 */
export function subscribeToAlerts(onUpdate, maxLimit = 50) {
  const q = query(
    collection(db, "alerts"),
    orderBy("timestamp", "desc"),
    limit(maxLimit)
  );
  return onSnapshot(q, (snapshot) => {
    const alerts = snapshot.docs.map((docSnap) => ({
      id: docSnap.id,
      ...docSnap.data()
    }));
    onUpdate(alerts);
  });
}

/**
 * Acknowledge an alert incident
 */
export async function acknowledgeAlert(alertId, officerEmail = "admin", notes = "Acknowledged") {
  const alertRef = doc(db, "alerts", alertId);
  await updateDoc(alertRef, {
    status: "ACKNOWLEDGED",
    acknowledged_by: officerEmail,
    notes: notes,
    acknowledged_at: new Date().toISOString()
  });
}

/**
 * Resolve an alert incident
 */
export async function resolveAlert(alertId, officerEmail = "admin", resolutionNotes = "Resolved by officer") {
  const alertRef = doc(db, "alerts", alertId);
  await updateDoc(alertRef, {
    status: "RESOLVED",
    resolved_by: officerEmail,
    notes: resolutionNotes,
    resolved_at: new Date().toISOString()
  });
}

// =====================================================================
// AUTHENTICATION & MULTI-DEVICE LAN SYNC METHODS
// Supports both Firebase Client SDK & FastAPI Backend across Wi-Fi (192.168.10.91:8000)
// =====================================================================

// Detect backend URL dynamically: Use Wi-Fi host IP if accessing from separate laptop
export const BACKEND_URL =
  typeof window !== "undefined" && window.location && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1"
    ? `http://${window.location.hostname}:8000`
    : "http://192.168.10.91:8000";

/**
 * Universal login function:
 * 1. Resolves username aliases ('aditya', 'admin') to email
 * 2. Attempts Firebase Client Auth
 * 3. Seamlessly falls back to FastAPI Backend (/api/v1/auth/login) on Wi-Fi LAN
 */
export async function loginUser(emailOrUsername, password) {
  const cleanId = String(emailOrUsername || "").trim();
  const cleanPwd = String(password || "").trim();

  // Normalize aliases for Firebase Auth
  let firebaseEmail = cleanId;
  if (!cleanId.includes("@")) {
    if (cleanId.toLowerCase() === "aditya" || cleanId.toLowerCase() === "admin") {
      firebaseEmail = "awsdevopskumar2026@gmail.com";
    } else {
      firebaseEmail = `${cleanId.toLowerCase()}@custodyband.com`;
    }
  }

  // 1. Try Firebase Auth
  try {
    const cred = await signInWithEmailAndPassword(auth, firebaseEmail, cleanPwd);
    if (cred && cred.user) {
      if (typeof window !== "undefined") {
        const idToken = await cred.user.getIdToken();
        localStorage.setItem("auth_token", idToken);
        localStorage.setItem("user", JSON.stringify({
          email: cred.user.email,
          uid: cred.user.uid,
          role: "admin"
        }));
      }
      return cred.user;
    }
  } catch (fbErr) {
    console.warn("Firebase Auth attempt notice:", fbErr.message, "-> Falling back to Backend REST API...");
  }

  // 2. Direct FastAPI Backend REST Login (Wi-Fi LAN compatible)
  const candidateUrls = [
    `${BACKEND_URL}/api/v1/auth/login`,
    `${BACKEND_URL}/login`,
    "http://192.168.10.91:8000/api/v1/auth/login",
    "http://127.0.0.1:8000/api/v1/auth/login"
  ];

  for (const url of candidateUrls) {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: cleanId,
          email: cleanId,
          password: cleanPwd
        })
      });

      if (resp.ok) {
        const data = await resp.json();
        const token = data.access_token || data.token || data.accessToken;
        const user = data.user || data.data?.user || { email: cleanId, role: "admin" };
        if (typeof window !== "undefined") {
          localStorage.setItem("auth_token", token);
          localStorage.setItem("user", JSON.stringify(user));
        }
        return {
          email: user.email || cleanId,
          uid: user.id || cleanId,
          displayName: user.full_name || cleanId,
          accessToken: token,
          token: token,
          user: user
        };
      }
    } catch (netErr) {
      // Continue to next endpoint candidate
    }
  }

  throw new Error("Unable to log in. Please check your credentials (aditya / Admin@123) and ensure backend is running on 192.168.10.91:8000.");
}

/**
 * Direct backend REST API login helper
 */
export async function loginWithBackend(usernameOrEmail, password, hostUrl = BACKEND_URL) {
  const resp = await fetch(`${hostUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: usernameOrEmail,
      email: usernameOrEmail,
      password: password
    })
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || "Invalid login credentials");
  }
  const data = await resp.json();
  const token = data.access_token || data.token;
  if (typeof window !== "undefined") {
    localStorage.setItem("auth_token", token);
    localStorage.setItem("user", JSON.stringify(data.user));
  }
  return data;
}

export async function logoutUser() {
  try {
    await signOut(auth);
  } catch (e) {}
  if (typeof window !== "undefined") {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user");
  }
}

export function subscribeToAuth(onUserChange) {
  return onAuthStateChanged(auth, onUserChange);
}

export function getStoredToken() {
  if (typeof window !== "undefined") {
    return localStorage.getItem("auth_token");
  }
  return null;
}

export function getStoredUser() {
  if (typeof window !== "undefined") {
    const u = localStorage.getItem("user");
    return u ? JSON.parse(u) : null;
  }
  return null;
}

// =====================================================================
// JOURNEY & TRAVEL DISTANCE TRACKING METHODS
// =====================================================================

export function haversineDistanceKm(lat1, lon1, lat2, lon2) {
  if (lat1 === lat2 && lon1 === lon2) return 0.0;
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Number((R * c).toFixed(3));
}

export async function startJourney(deviceId, startPoint = null) {
  const journeyId = `journey_${deviceId}_${Date.now()}`;
  const nowIso = new Date().toISOString();
  const routeCoordinates = startPoint ? [startPoint] : [];

  const journeyData = {
    id: journeyId,
    journey_id: journeyId,
    device_id: deviceId,
    status: "ACTIVE",
    start_time: nowIso,
    end_time: null,
    start_location: startPoint,
    end_location: null,
    route_coordinates: routeCoordinates,
    total_distance_km: 0.0,
    duration_seconds: 0,
    duration_formatted: "00:00:00",
    points_count: routeCoordinates.length,
    created_at: nowIso,
    updated_at: nowIso
  };

  await setDoc(doc(db, "journeys", journeyId), journeyData);
  await setDoc(doc(db, "devices", deviceId, "journeys", journeyId), journeyData);
  await setDoc(doc(db, "devices", deviceId), { active_journey_id: journeyId, updated_at: nowIso }, { merge: true });
  return journeyData;
}

export async function addJourneyPoint(journeyId, deviceId, point) {
  const journeyRef = doc(db, "journeys", journeyId);
  const snap = await getDoc(journeyRef);
  if (!snap.exists()) return;

  const current = snap.data();
  if (current.status !== "ACTIVE") return;

  const route = current.route_coordinates || [];
  if (route.length > 0) {
    const prev = route[route.length - 1];
    if (prev.latitude === point.latitude && prev.longitude === point.longitude) return;
    const distDelta = haversineDistanceKm(prev.latitude, prev.longitude, point.latitude, point.longitude);
    if (distDelta < 0.003) return;
    current.total_distance_km = Number(((current.total_distance_km || 0) + distDelta).toFixed(3));
  }

  if (!current.start_location) {
    current.start_location = point;
  }

  route.push(point);
  current.route_coordinates = route;
  current.points_count = route.length;
  current.updated_at = new Date().toISOString();

  try {
    const st = new Date(current.start_time).getTime();
    const ct = new Date(point.timestamp || current.updated_at).getTime();
    const sec = Math.max(0, Math.floor((ct - st) / 1000));
    current.duration_seconds = sec;
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    current.duration_formatted = `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  } catch (e) {}

  await setDoc(doc(db, "journeys", journeyId), current, { merge: true });
  await setDoc(doc(db, "devices", deviceId, "journeys", journeyId), current, { merge: true });
}

export async function endJourney(journeyId, deviceId, endPoint = null) {
  const journeyRef = doc(db, "journeys", journeyId);
  const snap = await getDoc(journeyRef);
  if (!snap.exists()) return null;

  const current = snap.data();
  const nowIso = new Date().toISOString();
  const route = current.route_coordinates || [];
  const finalEnd = endPoint || (route.length > 0 ? route[route.length - 1] : null);

  let durSec = 0;
  let durFmt = "00:00:00";
  try {
    const st = new Date(current.start_time).getTime();
    const et = new Date(nowIso).getTime();
    durSec = Math.max(0, Math.floor((et - st) / 1000));
    const h = Math.floor(durSec / 3600);
    const m = Math.floor((durSec % 3600) / 60);
    const s = durSec % 60;
    durFmt = `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  } catch (e) {}

  const updatedJourney = {
    ...current,
    status: "COMPLETED",
    end_time: nowIso,
    end_location: finalEnd,
    duration_seconds: durSec,
    duration_formatted: durFmt,
    updated_at: nowIso
  };

  await setDoc(doc(db, "journeys", journeyId), updatedJourney, { merge: true });
  await setDoc(doc(db, "devices", deviceId, "journeys", journeyId), updatedJourney, { merge: true });
  await setDoc(doc(db, "devices", deviceId), { active_journey_id: null, updated_at: nowIso }, { merge: true });
  return updatedJourney;
}

export function subscribeToActiveJourney(deviceId, onUpdate) {
  const devDocRef = doc(db, "devices", deviceId);
  let unsubJourney = null;

  return onSnapshot(devDocRef, (snap) => {
    if (!snap.exists()) {
      onUpdate(null);
      return;
    }
    const data = snap.data();
    const activeId = data?.active_journey_id;
    if (!activeId) {
      if (unsubJourney) {
        unsubJourney();
        unsubJourney = null;
      }
      onUpdate(null);
      return;
    }

    if (unsubJourney) unsubJourney();
    unsubJourney = onSnapshot(doc(db, "journeys", activeId), (jSnap) => {
      if (jSnap.exists()) {
        onUpdate({ ...(jSnap.data()), id: jSnap.id });
      } else {
        onUpdate(null);
      }
    });
  });
}

export function subscribeToDeviceJourneys(deviceId, onUpdate, maxLimit = 20) {
  const q = query(
    collection(db, "devices", deviceId, "journeys"),
    orderBy("created_at", "desc"),
    limit(maxLimit)
  );
  return onSnapshot(
    q,
    (snapshot) => {
      const journeys = snapshot.docs.map((docSnap) => ({
        ...(docSnap.data()),
        id: docSnap.id
      }));
      onUpdate(journeys);
    },
    (err) => {
      console.warn("Firestore device journeys subscription note:", err.message);
    }
  );
}
