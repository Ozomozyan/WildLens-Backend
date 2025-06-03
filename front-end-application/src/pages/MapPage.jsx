/* ─── src/pages/MapPage.jsx ────────────────────────────────────────────── */
import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import L from "leaflet";
import Layout from "../components/Layout.jsx";
import { listPredictionLocations } from "../services/DataService.js";

import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

/* ---------- fix default icon URLs so Vite can find them ---------- */
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: new URL(
    "leaflet/dist/images/marker-icon-2x.png",
    import.meta.url,
  ).href,
  iconUrl: new URL(
    "leaflet/dist/images/marker-icon.png",
    import.meta.url,
  ).href,
  shadowUrl: new URL(
    "leaflet/dist/images/marker-shadow.png",
    import.meta.url,
  ).href,
});

export default function MapPage() {
  const [points, setPoints] = useState(null);
  const [error, setError] = useState(null);

  function fetchPoints() {
    listPredictionLocations()
      .then(setPoints)
      .catch(() => setError("Could not load map data."));
  }

  /* initial load */
  useEffect(fetchPoints, []);

  /* ------------- guards ------------- */
  if (error)
    return (
      <Layout>
        <p className="p-6 text-red-600">{error}</p>
      </Layout>
    );

  if (points === null)
    return (
      <Layout>
        <p className="p-6">Loading map…</p>
      </Layout>
    );

  if (points.length === 0)
    return (
      <Layout>
        <p className="p-6">No geolocated predictions yet.</p>
      </Layout>
    );

  /* ------------- page ------------- */
  return (
    <Layout>
      {/* wrapper = remaining viewport minus navbar height (≈ 64 px) */}
      <div className="relative h-[calc(100vh-64px)] w-full">
        {/* ↻ quick refresh (mobile-friendly) */}
        <button
          onClick={fetchPoints}
          className="absolute right-4 top-4 z-[1000] rounded bg-primary/90 px-3 py-1 text-xs font-medium text-white backdrop-blur
                     hover:bg-primary"
        >
          ↻ Refresh
        </button>

        <MapContainer
          center={[20, 0]}
          zoom={2}
          minZoom={2}
          scrollWheelZoom
          className="h-full w-full"
        >
          <TileLayer
            attribution="© OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MarkerClusterGroup chunkLoading>
            {points.map(
              (p, i) =>
                p.lat &&
                p.lon && (
                  <Marker key={i} position={[p.lat, p.lon]}>
                    <Popup>
                      <strong>{p.species_name}</strong>
                    </Popup>
                  </Marker>
                ),
            )}
          </MarkerClusterGroup>
        </MapContainer>
      </div>
    </Layout>
  );
}
