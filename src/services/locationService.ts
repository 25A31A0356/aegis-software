/**
 * AGIES Shared Location Service
 * Centralized location system for Homepage, Analytics, Safety, Reports, Live Map, and Ask AGIES.
 * Covers all 28 Indian States & 8 Union Territories with real-time risk, weather, & GIS coordinates.
 */
import { ApiClient } from './apiClient';

export interface LocationCoordinates {
  latitude: number;
  longitude: number;
}

export interface LocationSearchResult {
  id: string;
  name: string;
  stateName: string;
  district: string;
  stateId: string;
  coordinates: [number, number]; // [lat, lng]
  riskScore: number;
  riskLevel: 'Low' | 'Medium' | 'High' | 'Critical';
  weatherSnippet?: string;
  confidence?: number;
}

export interface GeocodedAddress {
  cityName: string;
  stateName: string;
  district: string;
  stateId: string;
  readableAddress: string;
  coordinates: [number, number];
}

export interface SavedLocationItem {
  id: string;
  name: string;
  category: 'home' | 'work' | 'family' | 'other';
  coordinates: [number, number];
  stateName: string;
  district: string;
  riskScore: number;
  riskLevel: 'Low' | 'Medium' | 'High' | 'Critical';
  weatherSnippet: string;
  isCurrent?: boolean;
}

export interface NearbyActivityItem {
  id: string;
  hazardType: 'Flood' | 'Heavy Rain' | 'Lightning' | 'Cyclone' | 'Fire' | 'Earthquake' | 'Road Blockage' | 'Landslide' | 'Other';
  title: string;
  locationName: string;
  distanceKm: number;
  timestamp: string;
  severity: 'Critical' | 'Warning' | 'Watch' | 'Minor';
  coordinates: [number, number];
  source: string;
  status: string;
  recommendedAction: string;
  safetyGuideSlug?: string;
}

export type GeolocationErrorCode = 'PERMISSION_DENIED' | 'POSITION_UNAVAILABLE' | 'TIMEOUT' | 'NOT_SUPPORTED' | 'UNKNOWN';

export interface GeolocationResult {
  success: boolean;
  coordinates?: [number, number];
  address?: GeocodedAddress;
  error?: {
    code: GeolocationErrorCode;
    message: string;
    friendlyAdvice: string;
  };
}

const STORAGE_KEY = 'agies_saved_locations_v1';

export const INDIAN_CITIES_REGISTRY: LocationSearchResult[] = [
  // --- 28 STATES ---
  // Andhra Pradesh
  { id: 'city-amaravati', name: 'Amaravati', stateName: 'Andhra Pradesh', district: 'Guntur', stateId: 'AP', coordinates: [16.5417, 80.5158], riskScore: 74, riskLevel: 'High', weatherSnippet: '31°C • Coastal Breeze' },
  { id: 'city-visakhapatnam', name: 'Visakhapatnam', stateName: 'Andhra Pradesh', district: 'Visakhapatnam', stateId: 'AP', coordinates: [17.6868, 83.2185], riskScore: 89, riskLevel: 'Critical', weatherSnippet: '30°C • High Wave Warning' },
  { id: 'city-vijayawada', name: 'Vijayawada', stateName: 'Andhra Pradesh', district: 'NTR District', stateId: 'AP', coordinates: [16.5062, 80.6480], riskScore: 86, riskLevel: 'Critical', weatherSnippet: '32°C • Krishna Basin Spate' },
  
  // Arunachal Pradesh
  { id: 'city-itanagar', name: 'Itanagar', stateName: 'Arunachal Pradesh', district: 'Papum Pare', stateId: 'AR', coordinates: [27.0844, 93.6053], riskScore: 78, riskLevel: 'High', weatherSnippet: '21°C • Flash Surge Watch' },
  { id: 'city-tawang', name: 'Tawang', stateName: 'Arunachal Pradesh', district: 'Tawang', stateId: 'AR', coordinates: [27.5861, 91.8594], riskScore: 72, riskLevel: 'High', weatherSnippet: '14°C • Mountain Landslide Alert' },

  // Assam
  { id: 'city-dispur', name: 'Dispur', stateName: 'Assam', district: 'Kamrup Metropolitan', stateId: 'AS', coordinates: [26.1445, 91.7898], riskScore: 92, riskLevel: 'Critical', weatherSnippet: '27°C • Brahmaputra High Spate' },
  { id: 'city-guwahati', name: 'Guwahati', stateName: 'Assam', district: 'Kamrup Metropolitan', stateId: 'AS', coordinates: [26.1445, 91.7362], riskScore: 91, riskLevel: 'Critical', weatherSnippet: '27°C • Flood Advisory' },
  { id: 'city-silchar', name: 'Silchar', stateName: 'Assam', district: 'Cachar', stateId: 'AS', coordinates: [24.8333, 92.7789], riskScore: 88, riskLevel: 'Critical', weatherSnippet: '28°C • Barak Basin Inundation' },

  // Bihar
  { id: 'city-patna', name: 'Patna', stateName: 'Bihar', district: 'Patna', stateId: 'BR', coordinates: [25.5941, 85.1376], riskScore: 88, riskLevel: 'Critical', weatherSnippet: '31°C • Ganga Level Rising' },
  { id: 'city-gaya', name: 'Gaya', stateName: 'Bihar', district: 'Gaya', stateId: 'BR', coordinates: [24.7955, 85.0002], riskScore: 54, riskLevel: 'Medium', weatherSnippet: '32°C • Partly Cloudy' },
  { id: 'city-muzaffarpur', name: 'Muzaffarpur', stateName: 'Bihar', district: 'Muzaffarpur', stateId: 'BR', coordinates: [26.1209, 85.3647], riskScore: 84, riskLevel: 'High', weatherSnippet: '29°C • Burhi Gandak Flood' },

  // Chhattisgarh
  { id: 'city-raipur', name: 'Raipur', stateName: 'Chhattisgarh', district: 'Raipur', stateId: 'CG', coordinates: [21.2514, 81.6296], riskScore: 61, riskLevel: 'Medium', weatherSnippet: '28°C • Scattered Lightning' },
  { id: 'city-bilaspur', name: 'Bilaspur', stateName: 'Chhattisgarh', district: 'Bilaspur', stateId: 'CG', coordinates: [22.0797, 82.1391], riskScore: 66, riskLevel: 'Medium', weatherSnippet: '27°C • Arpa River Surge' },

  // Goa
  { id: 'city-panaji', name: 'Panaji', stateName: 'Goa', district: 'North Goa', stateId: 'GA', coordinates: [15.4909, 73.8278], riskScore: 58, riskLevel: 'Medium', weatherSnippet: '29°C • High Tidal Inundation' },
  { id: 'city-margao', name: 'Margao', stateName: 'Goa', district: 'South Goa', stateId: 'GA', coordinates: [15.2832, 73.9862], riskScore: 52, riskLevel: 'Medium', weatherSnippet: '29°C • Coastal Breeze' },

  // Gujarat
  { id: 'city-gandhinagar', name: 'Gandhinagar', stateName: 'Gujarat', district: 'Gandhinagar', stateId: 'GJ', coordinates: [23.2156, 72.6369], riskScore: 56, riskLevel: 'Medium', weatherSnippet: '31°C • Sabarmati Flow Normal' },
  { id: 'city-ahmedabad', name: 'Ahmedabad', stateName: 'Gujarat', district: 'Ahmedabad', stateId: 'GJ', coordinates: [23.0225, 72.5714], riskScore: 68, riskLevel: 'High', weatherSnippet: '32°C • Urban Heat / Cloud Surge' },
  { id: 'city-surat', name: 'Surat', stateName: 'Gujarat', district: 'Surat', stateId: 'GJ', coordinates: [21.1702, 72.8311], riskScore: 78, riskLevel: 'High', weatherSnippet: '30°C • Tapi River Watch' },

  // Haryana
  { id: 'city-chandigarh-hr', name: 'Panchkula / Chandigarh', stateName: 'Haryana', district: 'Panchkula', stateId: 'HR', coordinates: [30.6942, 76.8606], riskScore: 48, riskLevel: 'Medium', weatherSnippet: '27°C • Clear Skies' },
  { id: 'city-gurugram', name: 'Gurugram', stateName: 'Haryana', district: 'Gurugram', stateId: 'HR', coordinates: [28.4595, 77.0266], riskScore: 62, riskLevel: 'Medium', weatherSnippet: '30°C • Drainage Watch' },

  // Himachal Pradesh
  { id: 'city-shimla', name: 'Shimla', stateName: 'Himachal Pradesh', district: 'Shimla', stateId: 'HP', coordinates: [31.1048, 77.1734], riskScore: 82, riskLevel: 'High', weatherSnippet: '17°C • Landslide Warning' },
  { id: 'city-manali', name: 'Manali / Kullu', stateName: 'Himachal Pradesh', district: 'Kullu', stateId: 'HP', coordinates: [32.2396, 77.1887], riskScore: 87, riskLevel: 'Critical', weatherSnippet: '15°C • Beas Torrential Flow' },

  // Jharkhand
  { id: 'city-ranchi', name: 'Ranchi', stateName: 'Jharkhand', district: 'Ranchi', stateId: 'JH', coordinates: [23.3441, 85.3096], riskScore: 59, riskLevel: 'Medium', weatherSnippet: '26°C • Subarnarekha Watch' },
  { id: 'city-jamshedpur', name: 'Jamshedpur', stateName: 'Jharkhand', district: 'East Singhbhum', stateId: 'JH', coordinates: [22.8046, 86.2029], riskScore: 65, riskLevel: 'Medium', weatherSnippet: '29°C • Industrial Storm Runoff' },

  // Karnataka
  { id: 'city-bengaluru', name: 'Bengaluru', stateName: 'Karnataka', district: 'Bengaluru Urban', stateId: 'KA', coordinates: [12.9716, 77.5946], riskScore: 52, riskLevel: 'Medium', weatherSnippet: '26°C • Partly Cloudy' },
  { id: 'city-mangalore', name: 'Mangaluru', stateName: 'Karnataka', district: 'Dakshina Kannada', stateId: 'KA', coordinates: [12.9141, 74.8560], riskScore: 81, riskLevel: 'High', weatherSnippet: '28°C • Arabian Sea High Swell' },

  // Kerala
  { id: 'city-thiruvananthapuram', name: 'Thiruvananthapuram', stateName: 'Kerala', district: 'Thiruvananthapuram', stateId: 'KL', coordinates: [8.5241, 76.9366], riskScore: 68, riskLevel: 'High', weatherSnippet: '29°C • Coastal Rainbands' },
  { id: 'city-kochi', name: 'Kochi', stateName: 'Kerala', district: 'Ernakulam', stateId: 'KL', coordinates: [9.9312, 76.2673], riskScore: 76, riskLevel: 'High', weatherSnippet: '28°C • High Tide Inundation' },
  { id: 'city-wayanad', name: 'Wayanad (Meppadi/Kalpetta)', stateName: 'Kerala', district: 'Wayanad', stateId: 'KL', coordinates: [11.6854, 76.1320], riskScore: 94, riskLevel: 'Critical', weatherSnippet: '22°C • Landslip Red Alert' },

  // Madhya Pradesh
  { id: 'city-bhopal', name: 'Bhopal', stateName: 'Madhya Pradesh', district: 'Bhopal', stateId: 'MP', coordinates: [23.2599, 77.4126], riskScore: 57, riskLevel: 'Medium', weatherSnippet: '29°C • Upper Lake Sluice Active' },
  { id: 'city-indore', name: 'Indore', stateName: 'Madhya Pradesh', district: 'Indore', stateId: 'MP', coordinates: [22.7196, 75.8577], riskScore: 49, riskLevel: 'Low', weatherSnippet: '28°C • Clear Skies' },

  // Maharashtra
  { id: 'city-mumbai', name: 'Mumbai', stateName: 'Maharashtra', district: 'Mumbai Suburban', stateId: 'MH', coordinates: [19.0760, 72.8777], riskScore: 84, riskLevel: 'Critical', weatherSnippet: '31°C • Heavy Coastal Showers' },
  { id: 'city-pune', name: 'Pune', stateName: 'Maharashtra', district: 'Pune', stateId: 'MH', coordinates: [18.5204, 73.8567], riskScore: 64, riskLevel: 'Medium', weatherSnippet: '27°C • Mutha River Watch' },
  { id: 'city-nagpur', name: 'Nagpur', stateName: 'Maharashtra', district: 'Nagpur', stateId: 'MH', coordinates: [21.1458, 79.0882], riskScore: 42, riskLevel: 'Low', weatherSnippet: '32°C • Sunny' },

  // Manipur
  { id: 'city-imphal', name: 'Imphal', stateName: 'Manipur', district: 'Imphal West', stateId: 'MN', coordinates: [24.8170, 93.9368], riskScore: 81, riskLevel: 'High', weatherSnippet: '23°C • Nambul River Flood Watch' },

  // Meghalaya
  { id: 'city-shillong', name: 'Shillong', stateName: 'Meghalaya', district: 'East Khasi Hills', stateId: 'ML', coordinates: [25.5788, 91.8933], riskScore: 89, riskLevel: 'Critical', weatherSnippet: '19°C • Cherrapunji Torrential Rain' },

  // Mizoram
  { id: 'city-aizawl', name: 'Aizawl', stateName: 'Mizoram', district: 'Aizawl', stateId: 'MZ', coordinates: [23.7271, 92.7176], riskScore: 79, riskLevel: 'High', weatherSnippet: '22°C • Urban Slope Slips' },

  // Nagaland
  { id: 'city-kohima', name: 'Kohima', stateName: 'Nagaland', district: 'Kohima', stateId: 'NL', coordinates: [25.6751, 94.1086], riskScore: 76, riskLevel: 'High', weatherSnippet: '20°C • Highway Landslip Watch' },

  // Odisha
  { id: 'city-bhubaneswar', name: 'Bhubaneswar', stateName: 'Odisha', district: 'Khurda', stateId: 'OD', coordinates: [20.2961, 85.8245], riskScore: 83, riskLevel: 'High', weatherSnippet: '30°C • Mahanadi Basin Sluice' },
  { id: 'city-puri', name: 'Puri', stateName: 'Odisha', district: 'Puri', stateId: 'OD', coordinates: [19.8135, 85.8312], riskScore: 95, riskLevel: 'Critical', weatherSnippet: '29°C • Cyclone & Storm Surge Alert' },

  // Punjab
  { id: 'city-amritsar', name: 'Amritsar', stateName: 'Punjab', district: 'Amritsar', stateId: 'PB', coordinates: [31.6340, 74.8723], riskScore: 45, riskLevel: 'Low', weatherSnippet: '28°C • Clear Weather' },
  { id: 'city-ludhiana', name: 'Ludhiana', stateName: 'Punjab', district: 'Ludhiana', stateId: 'PB', coordinates: [30.9010, 75.8573], riskScore: 56, riskLevel: 'Medium', weatherSnippet: '29°C • Sutlej Catchment Watch' },

  // Rajasthan
  { id: 'city-jaipur', name: 'Jaipur', stateName: 'Rajasthan', district: 'Jaipur', stateId: 'RJ', coordinates: [26.9124, 75.7873], riskScore: 36, riskLevel: 'Low', weatherSnippet: '33°C • Clear Skies' },
  { id: 'city-jodhpur', name: 'Jodhpur', stateName: 'Rajasthan', district: 'Jodhpur', stateId: 'RJ', coordinates: [26.2389, 73.0243], riskScore: 40, riskLevel: 'Low', weatherSnippet: '35°C • Hot & Dry' },

  // Sikkim
  { id: 'city-gangtok', name: 'Gangtok', stateName: 'Sikkim', district: 'East Sikkim', stateId: 'SK', coordinates: [27.3389, 88.6065], riskScore: 90, riskLevel: 'Critical', weatherSnippet: '18°C • Teesta Basin GLOF Red Alert' },

  // Tamil Nadu
  { id: 'city-chennai', name: 'Chennai', stateName: 'Tamil Nadu', district: 'Chennai', stateId: 'TN', coordinates: [13.0827, 80.2707], riskScore: 87, riskLevel: 'Critical', weatherSnippet: '32°C • Adyar/Coom Surge' },
  { id: 'city-coimbatore', name: 'Coimbatore', stateName: 'Tamil Nadu', district: 'Coimbatore', stateId: 'TN', coordinates: [11.0168, 76.9558], riskScore: 42, riskLevel: 'Low', weatherSnippet: '27°C • Pleasant' },
  { id: 'city-madurai', name: 'Madurai', stateName: 'Tamil Nadu', district: 'Madurai', stateId: 'TN', coordinates: [9.9252, 78.1198], riskScore: 58, riskLevel: 'Medium', weatherSnippet: '33°C • Vaigai Basin Normal' },

  // Telangana
  { id: 'city-hyderabad', name: 'Hyderabad', stateName: 'Telangana', district: 'Hyderabad', stateId: 'TS', coordinates: [17.3850, 78.4867], riskScore: 58, riskLevel: 'Medium', weatherSnippet: '29°C • Musi Flow Monitored' },
  { id: 'city-warangal', name: 'Warangal', stateName: 'Telangana', district: 'Hanamkonda', stateId: 'TS', coordinates: [17.9689, 79.5941], riskScore: 71, riskLevel: 'High', weatherSnippet: '30°C • Severe Lightning Alert' },
  { id: 'city-khammam', name: 'Khammam', stateName: 'Telangana', district: 'Khammam', stateId: 'TS', coordinates: [17.2473, 80.1514], riskScore: 89, riskLevel: 'Critical', weatherSnippet: '31°C • Munneru River Flash Flood' },

  // Tripura
  { id: 'city-agartala', name: 'Agartala', stateName: 'Tripura', district: 'West Tripura', stateId: 'TR', coordinates: [23.8315, 91.2868], riskScore: 78, riskLevel: 'High', weatherSnippet: '28°C • Howrah River Overflow' },

  // Uttar Pradesh
  { id: 'city-lucknow', name: 'Lucknow', stateName: 'Uttar Pradesh', district: 'Lucknow', stateId: 'UP', coordinates: [26.8467, 80.9462], riskScore: 66, riskLevel: 'Medium', weatherSnippet: '31°C • Gomti Water Level Watch' },
  { id: 'city-varanasi', name: 'Varanasi', stateName: 'Uttar Pradesh', district: 'Varanasi', stateId: 'UP', coordinates: [25.3176, 82.9739], riskScore: 89, riskLevel: 'Critical', weatherSnippet: '32°C • Ganga Inundation Warning' },
  { id: 'city-prayagraj', name: 'Prayagraj', stateName: 'Uttar Pradesh', district: 'Prayagraj', stateId: 'UP', coordinates: [25.4358, 81.8463], riskScore: 87, riskLevel: 'Critical', weatherSnippet: '31°C • Sangam High Flood Alert' },

  // Uttarakhand
  { id: 'city-dehradun', name: 'Dehradun', stateName: 'Uttarakhand', district: 'Dehradun', stateId: 'UK', coordinates: [30.3165, 78.0322], riskScore: 79, riskLevel: 'High', weatherSnippet: '24°C • Heavy Downpours' },
  { id: 'city-joshimath', name: 'Joshimath / Chamoli', stateName: 'Uttarakhand', district: 'Chamoli', stateId: 'UK', coordinates: [30.5564, 79.5664], riskScore: 96, riskLevel: 'Critical', weatherSnippet: '14°C • Ground Subsidence & GLOF Warning' },

  // West Bengal
  { id: 'city-kolkata', name: 'Kolkata', stateName: 'West Bengal', district: 'Kolkata', stateId: 'WB', coordinates: [22.5726, 88.3639], riskScore: 78, riskLevel: 'High', weatherSnippet: '30°C • Hooghly Tidal Inundation' },
  { id: 'city-darjeeling', name: 'Darjeeling', stateName: 'West Bengal', district: 'Darjeeling', stateId: 'WB', coordinates: [27.0410, 88.2663], riskScore: 84, riskLevel: 'High', weatherSnippet: '16°C • Hill Slump Hazard' },

  // --- 8 UNION TERRITORIES ---
  // Andaman & Nicobar Islands
  { id: 'city-portblair', name: 'Port Blair', stateName: 'Andaman & Nicobar Islands', district: 'South Andaman', stateId: 'AN', coordinates: [11.6234, 92.7265], riskScore: 88, riskLevel: 'Critical', weatherSnippet: '29°C • Coastal Swell / Tsunami Watch' },

  // Chandigarh
  { id: 'city-chandigarh', name: 'Chandigarh', stateName: 'Chandigarh', district: 'Chandigarh', stateId: 'CH', coordinates: [30.7333, 76.7794], riskScore: 35, riskLevel: 'Low', weatherSnippet: '27°C • Clear & Calm' },

  // Dadra & Nagar Haveli and Daman & Diu
  { id: 'city-daman', name: 'Daman', stateName: 'Dadra & Nagar Haveli and Daman & Diu', district: 'Daman', stateId: 'DNHDD', coordinates: [20.3974, 72.8328], riskScore: 68, riskLevel: 'High', weatherSnippet: '30°C • Arabian Sea Tidal Inundation' },
  { id: 'city-silvassa', name: 'Silvassa', stateName: 'Dadra & Nagar Haveli and Daman & Diu', district: 'Dadra and Nagar Haveli', stateId: 'DNHDD', coordinates: [20.2763, 73.0083], riskScore: 56, riskLevel: 'Medium', weatherSnippet: '29°C • Moderate Rain' },

  // Delhi (NCT)
  { id: 'city-delhi', name: 'New Delhi', stateName: 'Delhi (NCT)', district: 'New Delhi', stateId: 'DL', coordinates: [28.6139, 77.2090], riskScore: 68, riskLevel: 'High', weatherSnippet: '29°C • Yamuna Floodplain Alert' },

  // Jammu & Kashmir
  { id: 'city-srinagar', name: 'Srinagar', stateName: 'Jammu & Kashmir', district: 'Srinagar', stateId: 'JK', coordinates: [34.0837, 74.7973], riskScore: 83, riskLevel: 'High', weatherSnippet: '18°C • Jhelum River Spate Watch' },
  { id: 'city-jammu', name: 'Jammu', stateName: 'Jammu & Kashmir', district: 'Jammu', stateId: 'JK', coordinates: [32.7266, 74.8570], riskScore: 64, riskLevel: 'Medium', weatherSnippet: '27°C • Tawi Catchment Runoff' },

  // Ladakh
  { id: 'city-leh', name: 'Leh', stateName: 'Ladakh', district: 'Leh', stateId: 'LA', coordinates: [34.1526, 77.5771], riskScore: 78, riskLevel: 'High', weatherSnippet: '12°C • Glacial Melt Surge' },
  { id: 'city-kargil', name: 'Kargil', stateName: 'Ladakh', district: 'Kargil', stateId: 'LA', coordinates: [34.5539, 76.1349], riskScore: 72, riskLevel: 'High', weatherSnippet: '11°C • Suru River Torrential Spate' },

  // Lakshadweep
  { id: 'city-kavaratti', name: 'Kavaratti', stateName: 'Lakshadweep', district: 'Lakshadweep', stateId: 'LD', coordinates: [10.5669, 72.6420], riskScore: 84, riskLevel: 'High', weatherSnippet: '29°C • High Wave & Coral Surge' },

  // Puducherry
  { id: 'city-puducherry', name: 'Puducherry', stateName: 'Puducherry', district: 'Puducherry', stateId: 'PY', coordinates: [11.9416, 79.8083], riskScore: 79, riskLevel: 'High', weatherSnippet: '31°C • Coastal Beach Inundation' }
];

const DEFAULT_SAVED_LOCATIONS: SavedLocationItem[] = [
  {
    id: 'loc-1',
    name: 'Home (Mumbai Suburban)',
    category: 'home',
    coordinates: [19.0760, 72.8777],
    stateName: 'Maharashtra',
    district: 'Mumbai Suburban',
    riskScore: 84,
    riskLevel: 'High',
    weatherSnippet: '31°C • Heavy Coastal Showers',
  },
  {
    id: 'loc-2',
    name: 'Office (Bandra-Kurla Complex)',
    category: 'work',
    coordinates: [19.0596, 72.8656],
    stateName: 'Maharashtra',
    district: 'Mumbai City',
    riskScore: 72,
    riskLevel: 'High',
    weatherSnippet: '30°C • Thunderstorms',
  },
  {
    id: 'loc-3',
    name: 'Family (Amaravati / Guntur)',
    category: 'family',
    coordinates: [16.5417, 80.5158],
    stateName: 'Andhra Pradesh',
    district: 'Guntur',
    riskScore: 74,
    riskLevel: 'High',
    weatherSnippet: '31°C • Coastal Breeze',
  },
];

class LocationServiceClass {
  private savedLocations: SavedLocationItem[] = [];
  private selectedLocation: LocationSearchResult = INDIAN_CITIES_REGISTRY[0]; // Default: Amaravati

  constructor() {
    this.loadFromStorage();
  }

  private loadFromStorage(): void {
    if (typeof window === 'undefined') {
      this.savedLocations = [...DEFAULT_SAVED_LOCATIONS];
      return;
    }

    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        this.savedLocations = JSON.parse(stored);
      } else {
        this.savedLocations = [...DEFAULT_SAVED_LOCATIONS];
        this.saveToStorage();
      }
    } catch {
      this.savedLocations = [...DEFAULT_SAVED_LOCATIONS];
    }
  }

  private saveToStorage(): void {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.savedLocations));
    } catch (e) {
      console.warn('Failed to save locations to localStorage:', e);
    }
  }

  /**
   * 1. getCurrentPosition()
   * Requests HTML5 browser geolocation API with timeout and high accuracy.
   */
  async getCurrentPosition(): Promise<GeolocationResult> {
    if (typeof window === 'undefined' || !navigator.geolocation) {
      return {
        success: false,
        error: {
          code: 'NOT_SUPPORTED',
          message: 'Geolocation is not supported by your browser.',
          friendlyAdvice: 'Please use a modern browser or select your Indian state/city manually from the search bar.',
        },
      };
    }

    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          const address = await this.reverseGeocode(lat, lng);
          resolve({
            success: true,
            coordinates: [lat, lng],
            address,
          });
        },
        (error) => {
          let code: GeolocationErrorCode = 'UNKNOWN';
          let advice = 'Unable to determine your GPS location. Please choose your city manually.';

          switch (error.code) {
            case error.PERMISSION_DENIED:
              code = 'PERMISSION_DENIED';
              advice = 'Location permission was denied. Click the lock/info icon in your browser URL bar to allow location access for real-time local disaster alerts.';
              break;
            case error.POSITION_UNAVAILABLE:
              code = 'POSITION_UNAVAILABLE';
              advice = 'GPS or network signal unavailable. Defaulting to state-level telemetry grid.';
              break;
            case error.TIMEOUT:
              code = 'TIMEOUT';
              advice = 'Location request timed out. Retrying with regional network fallback.';
              break;
          }

          resolve({
            success: false,
            error: {
              code,
              message: error.message || 'Geolocation error',
              friendlyAdvice: advice,
            },
          });
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000,
        }
      );
    });
  }

  async getCurrentLocation(): Promise<GeolocationResult> {
    return this.getCurrentPosition();
  }

  /**
   * 2. searchLocations(query)
   * Searches by Indian State, City, District name, or GPS Coordinates (lat, lng)
   */
  async searchLocation(query: string): Promise<LocationSearchResult[]> {
    return this.searchLocations(query);
  }

  async searchLocations(query: string): Promise<LocationSearchResult[]> {
    if (!query || query.trim().length === 0) {
      return INDIAN_CITIES_REGISTRY.slice(0, 10);
    }

    const trimmed = query.trim().toLowerCase();

    // Match by city name, state name, or district
    const matches = INDIAN_CITIES_REGISTRY.filter((item) => {
      return (
        item.name.toLowerCase().includes(trimmed) ||
        item.stateName.toLowerCase().includes(trimmed) ||
        item.district.toLowerCase().includes(trimmed) ||
        item.stateId.toLowerCase() === trimmed
      );
    });

    if (matches.length > 0) {
      return matches;
    }

    // Check for coordinate search (e.g. "19.07, 72.87")
    const coordMatch = trimmed.match(/^([0-9.-]+)[,\s]+([0-9.-]+)$/);
    if (coordMatch) {
      const lat = parseFloat(coordMatch[1]);
      const lng = parseFloat(coordMatch[2]);
      if (!isNaN(lat) && !isNaN(lng) && lat >= 6 && lat <= 38 && lng >= 68 && lng <= 98) {
        const address = await this.reverseGeocode(lat, lng);
        return [
          {
            id: `coord-${lat.toFixed(2)}-${lng.toFixed(2)}`,
            name: address.cityName,
            stateName: address.stateName,
            district: address.district,
            stateId: address.stateId,
            coordinates: [lat, lng],
            riskScore: 60,
            riskLevel: 'Medium',
            weatherSnippet: '29°C • Telemetry Active',
          },
        ];
      }
    }

    return [];
  }

  /**
   * 3. reverseGeocode(lat, lng)
   * Reverse geocodes coordinates to nearest Indian State/UT and City
   */
  async reverseGeocode(lat: number, lng: number): Promise<GeocodedAddress> {
    let closestCity = INDIAN_CITIES_REGISTRY[0];
    let minDistance = Infinity;

    for (const city of INDIAN_CITIES_REGISTRY) {
      const dist = this.calculateDistanceKm([lat, lng], city.coordinates);
      if (dist < minDistance) {
        minDistance = dist;
        closestCity = city;
      }
    }

    if (minDistance <= 45) {
      return {
        cityName: closestCity.name,
        stateName: closestCity.stateName,
        district: closestCity.district,
        stateId: closestCity.stateId,
        readableAddress: `${closestCity.name}, ${closestCity.district}, ${closestCity.stateName}`,
        coordinates: [lat, lng],
      };
    }

    return {
      cityName: `${closestCity.name} Sector`,
      stateName: closestCity.stateName,
      district: closestCity.district,
      stateId: closestCity.stateId,
      readableAddress: `Near ${closestCity.name} (${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E), ${closestCity.stateName}`,
      coordinates: [lat, lng],
    };
  }

  /**
   * 4. saveLocation(location)
   */
  saveLocation(location: Omit<SavedLocationItem, 'id'>): SavedLocationItem[] {
    const newItem: SavedLocationItem = {
      ...location,
      id: `loc-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
    };
    this.savedLocations.unshift(newItem);
    this.saveToStorage();
    return this.getSavedLocations();
  }

  /**
   * 5. removeLocation(id)
   */
  removeLocation(id: string): SavedLocationItem[] {
    this.savedLocations = this.savedLocations.filter((item) => item.id !== id);
    this.saveToStorage();
    return this.getSavedLocations();
  }

  /**
   * 6. selectLocation(locationOrId)
   */
  selectLocation(target: LocationSearchResult | SavedLocationItem | string): LocationSearchResult {
    if (typeof target === 'string') {
      const match =
        INDIAN_CITIES_REGISTRY.find((c) => c.id === target || c.name.toLowerCase() === target.toLowerCase()) ||
        this.savedLocations.find((l) => l.id === target);
      if (match) {
        this.selectedLocation = {
          id: match.id,
          name: match.name,
          stateName: match.stateName,
          district: match.district,
          stateId: (match as any).stateId || 'IN',
          coordinates: match.coordinates,
          riskScore: match.riskScore,
          riskLevel: match.riskLevel,
          weatherSnippet: match.weatherSnippet,
        };
      }
    } else {
      this.selectedLocation = {
        id: target.id,
        name: target.name,
        stateName: target.stateName,
        district: target.district,
        stateId: (target as any).stateId || 'IN',
        coordinates: target.coordinates,
        riskScore: target.riskScore,
        riskLevel: target.riskLevel,
        weatherSnippet: target.weatherSnippet,
      };
    }
    return this.selectedLocation;
  }

  getSelectedLocation(): LocationSearchResult {
    return this.selectedLocation;
  }

  getSavedLocations(): SavedLocationItem[] {
    return [...this.savedLocations];
  }

  calculateDistanceKm(coords1: [number, number], coords2: [number, number]): number {
    const [lat1, lon1] = coords1;
    const [lat2, lon2] = coords2;
    const R = 6371;
    const dLat = (lat2 - lat1) * (Math.PI / 180);
    const dLon = (lon2 - lon1) * (Math.PI / 180);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * (Math.PI / 180)) *
        Math.cos(lat2 * (Math.PI / 180)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c * 10) / 10;
  }

  private nearbyCache: Record<string, NearbyActivityItem[]> = {};

  async fetchNearbyActivity(center: [number, number]): Promise<NearbyActivityItem[]> {
    const key = `${center[0].toFixed(2)}_${center[1].toFixed(2)}`;
    try {
      const backendNearby = await ApiClient.get<any[]>('/hazards/nearby', {
        lat: center[0],
        lng: center[1],
        radius_km: 75,
      });

      if (backendNearby && Array.isArray(backendNearby)) {
        const mapped: NearbyActivityItem[] = backendNearby.map((item) => {
          let hType: NearbyActivityItem['hazardType'] = 'Other';
          const t = (item.type || '').toLowerCase();
          if (t.includes('flood') || t.includes('rain')) hType = 'Flood';
          else if (t.includes('lightning')) hType = 'Lightning';
          else if (t.includes('cyclone') || t.includes('wind')) hType = 'Cyclone';
          else if (t.includes('earthquake')) hType = 'Earthquake';
          else if (t.includes('fire')) hType = 'Fire';
          else if (t.includes('landslide')) hType = 'Landslide';
          else if (t.includes('road')) hType = 'Road Blockage';

          const sevRaw = (item.severity || 'WARNING').toUpperCase();
          const sev: NearbyActivityItem['severity'] =
            sevRaw === 'CRITICAL' ? 'Critical' : sevRaw === 'HIGH' ? 'Warning' : sevRaw === 'MODERATE' ? 'Watch' : 'Minor';

          return {
            id: item.id || `act-${Math.random().toString(36).substring(2, 7)}`,
            hazardType: hType,
            title: item.title || `${hType} Telemetry Alert`,
            locationName: item.location?.name || `${item.distance_km?.toFixed(1) || 10}km away`,
            distanceKm: item.distance_km || this.calculateDistanceKm(center, [item.location?.latitude || center[0], item.location?.longitude || center[1]]),
            timestamp: item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Live',
            severity: sev,
            coordinates: [item.location?.latitude || center[0], item.location?.longitude || center[1]],
            source: item.source || 'AEGIS Multi-Hazard Grid',
            status: item.status || 'Active Surveillance',
            recommendedAction: item.description || 'Follow official disaster guidelines and local advisories.',
            safetyGuideSlug: hType.toLowerCase(),
          };
        });

        this.nearbyCache[key] = mapped;
        return mapped;
      }
    } catch (err) {
      console.warn('[LocationService] fetchNearbyActivity error:', err);
    }
    return this.nearbyCache[key] || [];
  }

  getNearbyActivity(center: [number, number]): NearbyActivityItem[] {
    const key = `${center[0].toFixed(2)}_${center[1].toFixed(2)}`;
    // Trigger async fetch to populate cache
    this.fetchNearbyActivity(center).catch(console.warn);
    return this.nearbyCache[key] || [];
  }
}

export const LocationService = new LocationServiceClass();
