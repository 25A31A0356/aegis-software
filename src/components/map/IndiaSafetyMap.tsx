import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { HazardItem } from '../../types/hazard';
import { StateRiskData, SafeShelter, GeoScope } from '../../types/location';
import { SOSBeacon } from '../../types/sos';
import { SimulatedRoute } from '../../services/routingService';
import {
  AlertTriangle,
  Radio,
  Wind,
  Droplets,
  Flame,
  Shield,
  PhoneCall,
  Eye,
  Info,
  Layers,
  ChevronRight,
  Crosshair,
  Map as MapIcon,
} from 'lucide-react';

// Google Maps Style Teardrop Pin Marker
const createGooglePinIcon = (color: string, label: string, isPulsing: boolean = false) => {
  return L.divIcon({
    className: 'google-maps-pin',
    html: `
      <div class="relative flex flex-col items-center justify-center -translate-y-3 cursor-pointer group">
        ${isPulsing ? `<div class="absolute -top-1 w-8 h-8 rounded-full animate-ping opacity-40" style="background-color: ${color};"></div>` : ''}
        <svg class="w-7 h-7 drop-shadow-md transition-transform group-hover:scale-110" viewBox="0 0 24 24" fill="${color}" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
          <circle cx="12" cy="9" r="3.2" fill="white"/>
        </svg>
        <span class="absolute top-1.5 text-[8.5px] font-extrabold text-slate-900 font-mono tracking-tighter">${label}</span>
      </div>
    `,
    iconSize: [28, 36],
    iconAnchor: [14, 32],
    popupAnchor: [0, -32],
  });
};

// Google Maps Pulsing GPS Blue Dot Icon
const createGoogleGPSDotIcon = () => {
  return L.divIcon({
    className: 'google-gps-pulse-dot',
    html: `
      <div class="relative flex items-center justify-center">
        <div class="absolute w-8 h-8 rounded-full bg-blue-500/35 animate-ping"></div>
        <div class="w-4 h-4 rounded-full bg-blue-600 border-2 border-white shadow-md flex items-center justify-center">
          <div class="w-1.5 h-1.5 rounded-full bg-white"></div>
        </div>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
};

const createSOSIcon = () => {
  return L.divIcon({
    className: 'custom-sos-marker',
    html: `
      <div class="relative flex items-center justify-center">
        <div class="absolute w-9 h-9 rounded-full bg-red-600/30 animate-ping"></div>
        <div class="w-7 h-7 rounded-full bg-red-600 border-2 border-white shadow-elevated flex items-center justify-center text-white text-xs font-bold font-mono">
          SOS
        </div>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18],
  });
};

const createShelterIcon = () => {
  return L.divIcon({
    className: 'custom-shelter-marker',
    html: `
      <div class="w-5 h-5 rounded-md bg-indigo-600 border border-white shadow flex items-center justify-center text-white text-[9px] font-bold">
        🏠
      </div>
    `,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -11],
  });
};

// Map Recenter Controller
const MapRecenter: React.FC<{ center: [number, number]; zoom: number }> = ({ center, zoom }) => {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom, { animate: true });
  }, [center, zoom, map]);
  return null;
};

// Google Maps Floating Overlay Controls (Zoom + GPS Recenter + Sat/Map Switcher)
const GoogleMapOverlayControls: React.FC<{
  baseLayer: MapLayersState['baseLayer'];
  onToggleLayer: () => void;
  userLocation?: [number, number] | null;
}> = ({ baseLayer, onToggleLayer, userLocation }) => {
  const map = useMap();

  return (
    <>
      {/* Bottom-Left: Google Maps Satellite / Roadmap Toggle Box */}
      <div className="absolute bottom-4 left-4 z-400 pointer-events-auto">
        <button
          onClick={onToggleLayer}
          className="flex items-center gap-2 bg-white/95 backdrop-blur-xs hover:bg-white text-slate-800 px-3 py-2 rounded-xl shadow-card border border-slate-200 text-xs font-semibold transition-all hover:shadow-md"
          title="Toggle Google Maps Satellite / Streets"
        >
          <div className="w-6 h-6 rounded-md overflow-hidden border border-slate-300 shrink-0 shadow-inner flex items-center justify-center">
            {baseLayer === 'satellite' ? (
              <span className="text-[9px] font-bold text-slate-900 bg-slate-200 w-full h-full flex items-center justify-center">MAP</span>
            ) : (
              <span className="text-[9px] font-bold text-white bg-slate-900 w-full h-full flex items-center justify-center">SAT</span>
            )}
          </div>
          <span>{baseLayer === 'satellite' ? 'Google Streets' : 'Google Satellite'}</span>
        </button>
      </div>

      {/* Bottom-Right: Google Maps Zoom & GPS Buttons */}
      <div className="absolute bottom-4 right-4 z-400 flex flex-col gap-2 items-center pointer-events-auto">
        {userLocation && (
          <button
            onClick={() => map.flyTo(userLocation, 12, { animate: true, duration: 1.2 })}
            className="w-9 h-9 rounded-xl bg-white hover:bg-slate-50 text-slate-700 hover:text-blue-600 shadow-card border border-slate-200 flex items-center justify-center transition-all hover:scale-105"
            title="Recenter on My Live GPS Location"
          >
            <Crosshair className="w-4 h-4 text-blue-600" />
          </button>
        )}

        <div className="bg-white rounded-xl shadow-card border border-slate-200 overflow-hidden flex flex-col divide-y divide-slate-100">
          <button
            onClick={() => map.zoomIn()}
            className="w-9 h-8 flex items-center justify-center text-slate-700 hover:bg-slate-50 font-bold text-base transition-colors"
            title="Zoom in"
          >
            +
          </button>
          <button
            onClick={() => map.zoomOut()}
            className="w-9 h-8 flex items-center justify-center text-slate-700 hover:bg-slate-50 font-bold text-base transition-colors"
            title="Zoom out"
          >
            −
          </button>
        </div>
      </div>
    </>
  );
};

export interface MapLayersState {
  weatherRadar: boolean;
  isobarWinds: boolean;
  floodInundation: boolean;
  cycloneTrack: boolean;
  wildfireHotspots: boolean;
  earthquakes: boolean;
  sosBeacons: boolean;
  safeShelters: boolean;
  baseLayer: 'light' | 'dark' | 'satellite' | 'terrain';
}

interface IndiaSafetyMapProps {
  hazards: HazardItem[];
  states: StateRiskData[];
  sosBeacons: SOSBeacon[];
  shelters: SafeShelter[];
  activeRoute?: SimulatedRoute | null;
  layers: MapLayersState;
  selectedState?: StateRiskData | null;
  userLocation?: [number, number] | null;
  onSelectState?: (state: StateRiskData) => void;
  onSelectHazard?: (hazardId: string) => void;
  onSelectSOS?: (sosId: string) => void;
  onToggleBaseLayer?: () => void;
  scope?: GeoScope;
  heightClass?: string;
}

export const IndiaSafetyMap: React.FC<IndiaSafetyMapProps> = ({
  hazards,
  states,
  sosBeacons,
  shelters,
  activeRoute,
  layers,
  selectedState,
  userLocation,
  onSelectState,
  onSelectHazard,
  onSelectSOS,
  onToggleBaseLayer,
  scope = 'india',
  heightClass = 'h-[580px]',
}) => {
  const [mapCenter, setMapCenter] = useState<[number, number]>(() => userLocation || [21.5, 78.9]);
  const [mapZoom, setMapZoom] = useState<number>(() => (userLocation ? 9 : 5));
  const [currentBase, setCurrentBase] = useState<MapLayersState['baseLayer']>(layers.baseLayer);

  useEffect(() => {
    setCurrentBase(layers.baseLayer);
  }, [layers.baseLayer]);

  useEffect(() => {
    if (selectedState) {
      setMapCenter(selectedState.centerCoordinates);
      setMapZoom(7);
    } else if (userLocation) {
      setMapCenter(userLocation);
      setMapZoom(8);
    } else {
      setMapCenter([21.5, 78.9]);
      setMapZoom(5);
    }
  }, [selectedState, userLocation]);

  // Google Maps Tile Configuration (Streets, Satellite Hybrid, Terrain)
  const getGoogleTileConfig = () => {
    switch (currentBase) {
      case 'satellite':
        return {
          url: 'https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
          attribution: 'Map data &copy; Google Maps Imagery',
          subdomains: ['0', '1', '2', '3'],
          maxZoom: 20,
        };
      case 'terrain':
        return {
          url: 'https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
          attribution: 'Map data &copy; Google Maps Terrain',
          subdomains: ['0', '1', '2', '3'],
          maxZoom: 20,
        };
      case 'dark':
        return {
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
          attribution: 'Map data &copy; Google Maps & Dark Canvas',
          subdomains: ['0', '1', '2', '3'],
          maxZoom: 18,
        };
      case 'light':
      default:
        return {
          url: 'https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
          attribution: 'Map data &copy; Google Maps',
          subdomains: ['0', '1', '2', '3'],
          maxZoom: 20,
        };
    }
  };

  const tileConfig = getGoogleTileConfig();

  const handleToggleBase = () => {
    const next = currentBase === 'satellite' ? 'light' : 'satellite';
    setCurrentBase(next);
    if (onToggleBaseLayer) onToggleBaseLayer();
  };

  // Simulated Cyclone Track Points for Cyclone Vayu
  const cycloneTrackCoords: [number, number][] = [
    [16.2, 86.8], // Past T-24h
    [17.8, 86.2], // Past T-12h
    [19.2, 85.9], // Current Center
    [20.5, 85.5], // Forecast +12h (Landfall Puri)
    [21.8, 85.2], // Forecast +24h (Inland Cuttack/Balasore)
  ];

  return (
    <div className={`relative w-full ${heightClass} rounded-2xl overflow-hidden border border-slate-200 shadow-card bg-slate-100`}>
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        zoomControl={false}
        scrollWheelZoom={true}
        className="w-full h-full z-10"
      >
        <MapRecenter center={mapCenter} zoom={mapZoom} />

        {/* Google Maps Base Tile Layer */}
        <TileLayer
          key={currentBase}
          url={tileConfig.url}
          attribution={tileConfig.attribution}
          subdomains={tileConfig.subdomains}
          maxZoom={tileConfig.maxZoom}
        />

        {/* Google Maps Floating Overlay Controls */}
        <GoogleMapOverlayControls
          baseLayer={currentBase}
          onToggleLayer={handleToggleBase}
          userLocation={userLocation}
        />

        {/* 1. Doppler Weather Radar & Active Severe Convective Zones */}
        {layers.weatherRadar && (
          <>
            {hazards
              .filter((h) => h.category === 'flood' || h.category === 'thunderstorm' || h.category === 'cyclone')
              .map((h) => (
                <Circle
                  key={`radar-${h.id}`}
                  center={h.location.coordinates}
                  radius={(h.location.radiusKm || 40) * 1000}
                  pathOptions={{
                    color: h.severity === 'critical' ? '#DC2626' : '#D97706',
                    fillColor: h.severity === 'critical' ? '#EF4444' : '#F59E0B',
                    fillOpacity: 0.25,
                    weight: 1.5,
                  }}
                />
              ))}
          </>
        )}

        {/* 2. Active Severe Cyclone Impact Zones */}
        {layers.cycloneTrack && (
          <>
            {hazards
              .filter((h) => h.category === 'cyclone')
              .map((h) => (
                <Circle
                  key={`cyclone-${h.id}`}
                  center={h.location.coordinates}
                  radius={(h.location.radiusKm || 60) * 1000}
                  pathOptions={{
                    color: '#DC2626',
                    fillColor: '#FEF08A',
                    fillOpacity: 0.2,
                    weight: 2,
                    dashArray: '4, 4',
                  }}
                />
              ))}
          </>
        )}

        {/* Real User GPS Location Indicator (Google Maps Blue Dot) */}
        {userLocation && (
          <Marker position={userLocation} icon={createGoogleGPSDotIcon()}>
            <Popup>
              <div className="p-2.5 font-sans text-xs max-w-xs">
                <div className="flex items-center gap-1.5 font-bold text-blue-700 border-b border-blue-100 pb-1 mb-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping" />
                  <span>📍 Your Real Live GPS Location</span>
                </div>
                <div className="text-[11px] text-slate-600 font-mono">
                  Coordinates: [{userLocation[0].toFixed(4)}°N, {userLocation[1].toFixed(4)}°E]
                </div>
                <div className="text-[10px] text-slate-400 mt-1">
                  Google Maps calibration locked to your sector.
                </div>
              </div>
            </Popup>
          </Marker>
        )}

        {/* 3. State Risk Markers (Google Pins) */}
        {states.map((st) => {
          const color =
            st.riskLevel === 'critical'
              ? '#EA4335' // Google Red
              : st.riskLevel === 'warning'
              ? '#FBBC04' // Google Amber
              : st.riskLevel === 'moderate'
              ? '#F2994A'
              : '#34A853'; // Google Green

          return (
            <Marker
              key={st.id}
              position={st.centerCoordinates}
              icon={createGooglePinIcon(color, st.id, st.riskLevel === 'critical')}
              eventHandlers={{
                click: () => onSelectState && onSelectState(st),
              }}
            >
              <Popup>
                <div className="p-3 max-w-xs font-sans">
                  <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2 mb-2">
                    <div className="font-bold text-sm text-slate-900">{st.name}</div>
                    <span
                      className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded ${
                        st.riskLevel === 'critical'
                          ? 'bg-red-100 text-red-700'
                          : st.riskLevel === 'warning'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      {st.riskLevel}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mb-2 leading-relaxed">
                    <strong>Primary Threat:</strong> {st.primaryThreat}
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-[11px] font-mono bg-slate-50 p-2 rounded-lg border border-slate-100 mb-2.5">
                    <div>
                      <span className="text-slate-400 block text-[10px]">TEMP / COND</span>
                      <span className="font-semibold text-slate-800">{st.currentTemp}°C</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">ACTIVE HAZARDS</span>
                      <span className="font-semibold text-slate-800">{st.activeHazardsCount} active</span>
                    </div>
                  </div>
                  <button
                    onClick={() => onSelectState && onSelectState(st)}
                    className="w-full bg-slate-900 hover:bg-blue-600 text-white text-xs font-semibold py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <span>View State Risk Brief</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* 4. Active Hazard Incident & Warning Pins */}
        {hazards.map((hz) => {
          const color =
            hz.severity === 'critical'
              ? '#EA4335'
              : hz.severity === 'warning'
              ? '#FBBC04'
              : '#4285F4';

          return (
            <React.Fragment key={hz.id}>
              {/* Hazard Impact Radius Ring */}
              {hz.location.radiusKm && (
                <Circle
                  center={hz.location.coordinates}
                  radius={hz.location.radiusKm * 1000}
                  pathOptions={{
                    color,
                    fillColor: color,
                    fillOpacity: 0.12,
                    weight: 1.5,
                  }}
                />
              )}

              <Marker
                position={hz.location.coordinates}
                icon={createGooglePinIcon(color, hz.nature[0].toUpperCase(), hz.severity === 'critical')}
                eventHandlers={{
                  click: () => onSelectHazard && onSelectHazard(hz.id),
                }}
              >
                <Popup>
                  <div className="p-3 max-w-sm font-sans">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded ${
                          hz.severity === 'critical' ? 'bg-red-600 text-white' : 'bg-amber-600 text-white'
                        }`}
                      >
                        {hz.nature.toUpperCase()}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">{hz.id}</span>
                    </div>
                    <h4 className="font-bold text-xs text-slate-900 mb-1 leading-snug">
                      {hz.title}
                    </h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed line-clamp-3 mb-2">
                      {hz.headline}
                    </p>
                    <div className="text-[10px] text-slate-500 font-mono border-t border-slate-100 pt-1.5 flex items-center justify-between">
                      <span>{hz.location.district}, {hz.location.state}</span>
                      <button
                        onClick={() => onSelectHazard && onSelectHazard(hz.id)}
                        className="text-blue-600 font-bold hover:underline"
                      >
                        Full Details →
                      </button>
                    </div>
                  </div>
                </Popup>
              </Marker>
            </React.Fragment>
          );
        })}

        {/* 5. SOS Beacons (Real Active Beacons Only) */}
        {layers.sosBeacons &&
          sosBeacons.map((sos) => (
            <Marker
              key={sos.id}
              position={sos.coordinates}
              icon={createSOSIcon()}
              eventHandlers={{
                click: () => onSelectSOS && onSelectSOS(sos.id),
              }}
            >
              <Popup>
                <div className="p-3 max-w-xs font-sans">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-mono font-bold bg-red-600 text-white px-2 py-0.5 rounded">
                      {sos.id}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500 uppercase">
                      {sos.triageStatus}
                    </span>
                  </div>
                  <h4 className="font-bold text-xs text-slate-900 mb-1">
                    {sos.emergencyTitle}
                  </h4>
                  <div className="text-[11px] text-slate-600 mb-2">
                    📍 {sos.locationName}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono bg-red-50 p-2 rounded border border-red-100 mb-2">
                    Persons trapped: <strong>{sos.personsCount}</strong> • Battery: {sos.batteryPercent}% • GPS ±{sos.gpsAccuracyMeters}m
                  </div>
                  <button
                    onClick={() => onSelectSOS && onSelectSOS(sos.id)}
                    className="w-full bg-red-600 hover:bg-red-700 text-white text-xs font-bold py-1.5 rounded-lg transition-colors flex items-center justify-center gap-1.5"
                  >
                    <PhoneCall className="w-3.5 h-3.5" />
                    Open Dispatch Triage
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}

        {/* 6. Evacuation Shelters & Relief Camps */}
        {layers.safeShelters &&
          shelters.map((sh) => (
            <Marker key={sh.id} position={sh.coordinates} icon={createShelterIcon()}>
              <Popup>
                <div className="p-2.5 max-w-xs font-sans text-xs">
                  <div className="font-bold text-indigo-700 mb-1 flex items-center gap-1">
                    <span>🏠 {sh.name}</span>
                  </div>
                  <div className="text-[11px] text-slate-600 mb-1.5">
                    📍 {sh.district}, {sh.state}
                  </div>
                  <div className="bg-indigo-50 p-1.5 rounded text-[10px] font-mono text-indigo-900 mb-2">
                    Capacity: <strong>{sh.currentOccupancy}/{sh.capacityPersons}</strong> ({sh.status})
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    Emergency Contact: <strong>{sh.contactNumber}</strong>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

        {/* 7. Active Emergency Dispatch Simulation Route */}
        {activeRoute && (
          <>
            <Polyline
              positions={activeRoute.waypoints}
              pathOptions={{
                color: '#2563EB',
                weight: 5,
                opacity: 0.9,
                lineCap: 'round',
                lineJoin: 'round',
              }}
            />
            {/* Responder Staging Start Pin */}
            <Marker
              position={activeRoute.waypoints[0]}
              icon={createGooglePinIcon('#2563EB', 'START')}
            >
              <Popup>
                <div className="p-2 text-xs font-sans">
                  <strong>Responder Staging Depot</strong>
                  <div className="text-slate-500 text-[10px]">Staging Area</div>
                </div>
              </Popup>
            </Marker>
          </>
        )}
      </MapContainer>
    </div>
  );
};
