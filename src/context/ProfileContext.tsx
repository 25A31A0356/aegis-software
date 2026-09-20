import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  EmergencyProfile,
  FamilyContact,
  DEFAULT_EMERGENCY_PROFILE,
  DEFAULT_FAMILY_CONTACTS,
} from '../types/profile';
import { ApiClient } from '../services/apiClient';

interface ProfileContextType {
  profile: EmergencyProfile;
  language: string;
  setLanguage: (lang: string) => void;
  colorScheme: 'light' | 'dark';
  setColorScheme: (scheme: 'light' | 'dark') => void;
  notificationsEnabled: boolean;
  setNotificationsEnabled: (enabled: boolean) => void;
  liveLocationEnabled: boolean;
  setLiveLocationEnabled: (enabled: boolean) => void;
  updateProfile: (updates: Partial<EmergencyProfile>) => void;
  addFamilyContact: (contact: Omit<FamilyContact, 'id'>) => void;
  updateFamilyContact: (id: string, contact: Partial<FamilyContact>) => void;
  removeFamilyContact: (id: string) => void;
  resetToDefaults: () => void;
}

const STORAGE_KEY = 'aegis_user_emergency_profile';
const PREFS_KEY = 'aegis_user_app_preferences';

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

export const ProfileProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [profile, setProfile] = useState<EmergencyProfile>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return {
          ...DEFAULT_EMERGENCY_PROFILE,
          ...parsed,
          familyContacts: parsed.familyContacts || DEFAULT_FAMILY_CONTACTS,
        };
      }
    } catch {
      // ignore
    }
    return DEFAULT_EMERGENCY_PROFILE;
  });

  const [language, setLanguageState] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(`${PREFS_KEY}_lang`);
      if (saved) return saved;
    } catch {}
    return 'en';
  });

  const [colorScheme, setColorSchemeState] = useState<'light' | 'dark'>(() => {
    try {
      const saved = localStorage.getItem(`${PREFS_KEY}_theme`);
      if (saved === 'dark' || saved === 'light') return saved;
      if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
    } catch {}
    return 'light';
  });

  const [notificationsEnabled, setNotificationsEnabledState] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(`${PREFS_KEY}_notif`);
      if (saved !== null) return saved === 'true';
    } catch {}
    return true;
  });

  const [liveLocationEnabled, setLiveLocationEnabledState] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(`${PREFS_KEY}_loc`);
      if (saved !== null) return saved === 'true';
    } catch {}
    return true;
  });

  // Apply dark mode CSS class to root HTML element
  useEffect(() => {
    if (typeof document !== 'undefined') {
      if (colorScheme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      try {
        localStorage.setItem(`${PREFS_KEY}_theme`, colorScheme);
      } catch {}
    }
  }, [colorScheme]);

  // Sync profile changes to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
    } catch {}
  }, [profile]);

  const setLanguage = (lang: string) => {
    setLanguageState(lang);
    try {
      localStorage.setItem(`${PREFS_KEY}_lang`, lang);
    } catch {}
  };

  const setColorScheme = (scheme: 'light' | 'dark') => {
    setColorSchemeState(scheme);
  };

  const setNotificationsEnabled = (enabled: boolean) => {
    setNotificationsEnabledState(enabled);
    try {
      localStorage.setItem(`${PREFS_KEY}_notif`, String(enabled));
    } catch {}
  };

  const setLiveLocationEnabled = (enabled: boolean) => {
    setLiveLocationEnabledState(enabled);
    try {
      localStorage.setItem(`${PREFS_KEY}_loc`, String(enabled));
    } catch {}
  };

  const updateProfile = (updates: Partial<EmergencyProfile>) => {
    setProfile((prev) => {
      const updated = {
        ...prev,
        ...updates,
      };
      return updated;
    });

    // Optionally sync with backend if authenticated
    ApiClient.post('/auth/preferences', {
      full_name: updates.fullName || profile.fullName,
      phone: updates.phoneNumber || profile.phoneNumber,
      blood_group: updates.bloodGroup || profile.bloodGroup,
      medical_notes: updates.medicalNotes || profile.medicalNotes,
      household_count: updates.peopleCount || profile.peopleCount,
    }).catch(() => {
      // Offline / guest mode fallback
    });
  };

  const addFamilyContact = (contact: Omit<FamilyContact, 'id'>) => {
    const newContact: FamilyContact = {
      ...contact,
      id: `fam-${Date.now()}`,
    };
    setProfile((prev) => ({
      ...prev,
      familyContacts: [...prev.familyContacts, newContact],
    }));
  };

  const updateFamilyContact = (id: string, updates: Partial<FamilyContact>) => {
    setProfile((prev) => ({
      ...prev,
      familyContacts: prev.familyContacts.map((c) => (c.id === id ? { ...c, ...updates } : c)),
    }));
  };

  const removeFamilyContact = (id: string) => {
    setProfile((prev) => ({
      ...prev,
      familyContacts: prev.familyContacts.filter((c) => c.id !== id),
    }));
  };

  const resetToDefaults = () => {
    setProfile(DEFAULT_EMERGENCY_PROFILE);
    setLanguageState('en');
    setColorSchemeState('light');
    setNotificationsEnabledState(true);
    setLiveLocationEnabledState(true);
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(`${PREFS_KEY}_lang`);
      localStorage.removeItem(`${PREFS_KEY}_theme`);
      localStorage.removeItem(`${PREFS_KEY}_notif`);
      localStorage.removeItem(`${PREFS_KEY}_loc`);
    } catch {}
  };

  return (
    <ProfileContext.Provider
      value={{
        profile,
        language,
        setLanguage,
        colorScheme,
        setColorScheme,
        notificationsEnabled,
        setNotificationsEnabled,
        liveLocationEnabled,
        setLiveLocationEnabled,
        updateProfile,
        addFamilyContact,
        updateFamilyContact,
        removeFamilyContact,
        resetToDefaults,
      }}
    >
      {children}
    </ProfileContext.Provider>
  );
};

export const useProfile = (): ProfileContextType => {
  const context = useContext(ProfileContext);
  if (!context) {
    throw new Error('useProfile must be used within a ProfileProvider');
  }
  return context;
};
