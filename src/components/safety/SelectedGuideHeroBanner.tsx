import React, { useState, useEffect } from 'react';
import {
  Bookmark,
  Check,
  ArrowRight,
  Shield,
  Sparkles,
  Radio,
  FileCheck,
} from 'lucide-react';
import { SafetyGuideItem } from '../../data/safetyGuidesData';

interface SelectedGuideHeroBannerProps {
  guide: SafetyGuideItem;
}

export const SelectedGuideHeroBanner: React.FC<SelectedGuideHeroBannerProps> = ({ guide }) => {
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    // Check local storage persistence
    try {
      const savedGuides = JSON.parse(
        localStorage.getItem('aegis_saved_guides') || localStorage.getItem('agies_saved_guides') || '[]'
      );
      setIsSaved(savedGuides.includes(guide.id));
    } catch {
      setIsSaved(false);
    }
  }, [guide.id]);

  const handleToggleSave = () => {
    try {
      const savedGuides: string[] = JSON.parse(
        localStorage.getItem('aegis_saved_guides') || localStorage.getItem('agies_saved_guides') || '[]'
      );
      let updated: string[] = [];
      if (savedGuides.includes(guide.id)) {
        updated = savedGuides.filter((id) => id !== guide.id);
        setIsSaved(false);
      } else {
        updated = [...savedGuides, guide.id];
        setIsSaved(true);
      }
      localStorage.setItem('aegis_saved_guides', JSON.stringify(updated));
    } catch {
      setIsSaved(!isSaved);
    }
  };

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-[#075B8A] via-[#0B6E9E] to-[#054366] text-white rounded-[24px] p-6 sm:p-8 shadow-elevated border border-white/10 mb-6">
      {/* Subtle Glow Overlays */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-[#18C3D0]/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-60 h-60 bg-[#45C79A]/10 rounded-full blur-2xl pointer-events-none" />

      <div className="relative z-10 space-y-3 max-w-4xl">
        {/* Top Tag & Status Badges */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E94B68] text-white text-[10px] font-mono font-bold uppercase shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
            <span>{guide.statusTag}</span>
          </span>
          <span className="px-3 py-1 rounded-full bg-white/15 text-[#D3E8F4] text-[10px] font-mono font-bold uppercase border border-white/15">
            SELECTED GUIDE
          </span>
        </div>

        {/* Title */}
        <h2 className="text-2xl sm:text-4xl font-black tracking-tight text-white font-sans capitalize pt-1">
          {guide.name} safety guide
        </h2>

        {/* Tagline / Core Guidance */}
        <p className="text-sm sm:text-base text-[#EDFAFC] font-medium leading-relaxed max-w-3xl">
          {guide.tagline}
        </p>

        {/* Action Button: Save This Guide */}
        <div className="pt-3">
          <button
            onClick={handleToggleSave}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-bold transition-all shadow-md active:scale-[0.98] ${
              isSaved
                ? 'bg-[#45C79A] text-[#075B8A] shadow-[#45C79A]/20'
                : 'bg-[#18C3D0] hover:bg-[#15B0BC] text-[#075B8A] shadow-[#18C3D0]/25'
            }`}
          >
            {isSaved ? (
              <>
                <Check className="w-4 h-4 text-[#075B8A]" />
                <span>Saved to Offline Guides</span>
              </>
            ) : (
              <>
                <Bookmark className="w-4 h-4 text-[#075B8A]" />
                <span>Save this guide</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
