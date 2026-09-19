export interface FamilyContact {
  id: string;
  name: string;
  phone: string;
  relationship: string;
  isPrimary?: boolean;
  notes?: string;
}

export interface EmergencyProfile {
  fullName: string;
  phoneNumber: string;
  bloodGroup: string;
  medicalNotes: string;
  peopleCount: number;
  familyContacts: FamilyContact[];
  customSosMessage?: string;
  customSafeMessage?: string;
}

export interface LanguageOption {
  code: string;
  label: string;
  native: string;
}

export const APP_LANGUAGES: LanguageOption[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिंदी' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
];

export const BLOOD_GROUPS = ['O+', 'A+', 'B+', 'AB+', 'O-', 'A-', 'B-', 'AB-'];

export const DEFAULT_FAMILY_CONTACTS: FamilyContact[] = [
  {
    id: 'fam-1',
    name: 'Priya Sharma',
    phone: '+91 98765 43210',
    relationship: 'Spouse',
    isPrimary: true,
    notes: 'Living at home address',
  },
  {
    id: 'fam-2',
    name: 'Ramesh Kumar Sharma',
    phone: '+91 98765 11223',
    relationship: 'Father',
    isPrimary: false,
    notes: 'Senior citizen',
  },
  {
    id: 'fam-3',
    name: 'Sunita Sharma',
    phone: '+91 98765 22334',
    relationship: 'Mother',
    isPrimary: false,
    notes: 'Senior citizen',
  },
];

export const DEFAULT_EMERGENCY_PROFILE: EmergencyProfile = {
  fullName: 'Aarav Sharma',
  phoneNumber: '+91 98765 00000',
  bloodGroup: 'O+',
  medicalNotes: 'No known chronic allergies. Fully vaccinated.',
  peopleCount: 3,
  familyContacts: DEFAULT_FAMILY_CONTACTS,
  customSosMessage: 'EMERGENCY SOS: I need immediate help! Please dispatch rescue to my location.',
  customSafeMessage: 'I am safe and secure. Sharing my location with family through AEGIS ALERT.',
};
