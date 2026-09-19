import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  X,
  Send,
  Sparkles,
  Bot,
  User,
  Shield,
  HelpCircle,
  PhoneCall,
  MapPin,
  ChevronRight,
  ExternalLink,
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  Compass,
} from 'lucide-react';
import { useLocation } from '../../context/LocationContext';
import { useDataProvider } from '../../context/DataProviderContext';
import { HazardService } from '../../services/hazardService';
import { AIService, AIChatResponse, AISuggestedAction, AIChatContext } from '../../services/aiService';
import { DataStatusIndicator } from './DataStatusIndicator';

interface ChatMessage {
  id: string;
  sender: 'bot' | 'user';
  text: string;
  timestamp: string;
  sources?: string[];
  safetyLevel?: string;
  suggestedActions?: AISuggestedAction[];
}

interface FloatingAskAEGISProps {
  activeTab?: string;
  selectedHazard?: string | null;
  onNavigate?: (tab: string) => void;
}

export type FloatingAskAGIESProps = FloatingAskAEGISProps;

const SUGGESTED_PROMPTS = [
  'What is my current risk?',
  'What should I do during a flood?',
  'Find nearby safe places.',
  'Explain this alert.',
  'What does this radar layer mean?',
  'Help me report an incident.',
];

export const FloatingAskAEGIS: React.FC<FloatingAskAEGISProps> = ({
  activeTab = 'homepage',
  selectedHazard = null,
  onNavigate,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [inputQuery, setInputQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const { weather, selectedState, userCoordinates } = useLocation();
  const { dataMode, isLiveMode } = useDataProvider();

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-msg',
      sender: 'bot',
      text: 'How can I help you stay safe?',
      timestamp: 'Just now',
      sources: ['National Disaster Management Authority (NDMA)', 'IMD India Grid'],
      safetyLevel: 'NORMAL',
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen, isTyping]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputQuery).trim();
    if (!text) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputQuery('');
    setIsTyping(true);

    // Build rich context from global application state
    const liveHazards = HazardService.getAllHazards();
    const activeAlerts = liveHazards.slice(0, 3).map((h) => `${h.category.toUpperCase()}: ${h.title}`);
    const nearbyHazards = liveHazards.slice(0, 4).map((h) => ({
      title: h.title,
      category: h.category,
      severity: h.severity,
      distance: h.location?.coordinates ? 'Nearby (Sector Watch)' : 'Regional',
    }));

    const chatContext: AIChatContext = {
      pageContext: activeTab,
      locationName: weather?.cityName || selectedState?.name || 'India Region',
      coordinates: userCoordinates || undefined,
      selectedHazard: selectedHazard || null,
      dataMode,
      currentRisk: {
        score: selectedState?.riskScore || 72,
        level: selectedState?.riskLevel || 'High Risk',
      },
      currentWeather: weather
        ? {
            temperature: weather.temp,
            condition: weather.condition,
            humidity: weather.humidity,
            windSpeed: weather.windSpeed,
            rainProbability: weather.rainProbability,
          }
        : undefined,
      activeAlerts,
      nearbyHazards,
    };

    try {
      const response: AIChatResponse = await AIService.sendMessage({
        message: text,
        context: chatContext,
      });

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: response.answer,
        timestamp: response.timestamp,
        sources: response.sources,
        safetyLevel: response.safetyLevel,
        suggestedActions: response.suggestedActions,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error('[Ask AGIES] Error processing message:', err);
      const fallbackMsg: ChatMessage = {
        id: `bot-fallback-${Date.now()}`,
        sender: 'bot',
        text: '⚠️ Unable to connect to the secure AI grid at this moment. For immediate life safety emergencies, please call **112** (National Emergency) or **1078** (NDMA Helpline).',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: ['National Emergency Response System'],
        safetyLevel: 'CRITICAL',
      };
      setMessages((prev) => [...prev, fallbackMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleActionClick = (action: AISuggestedAction) => {
    if (action.actionType === 'call' && action.payload) {
      window.location.href = `tel:${action.payload}`;
    } else if (action.actionTab && onNavigate) {
      onNavigate(action.actionTab);
      // On mobile, close or minimize chat so user can view navigated page
      if (window.innerWidth < 640) {
        setIsOpen(false);
      }
    } else if (action.actionType === 'hazard_select' && action.payload) {
      handleSendMessage(action.payload);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 select-none print:hidden">
      {/* Floating Chat Panel */}
      {isOpen && (
        <div className="mb-3 w-[370px] sm:w-[420px] h-[540px] max-sm:fixed max-sm:inset-x-3 max-sm:bottom-20 max-sm:w-auto max-sm:h-[75vh] bg-white rounded-[24px] shadow-float border border-[#DCEBED] flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200 z-50">
          {/* Header */}
          <div className="bg-[#075B8A] text-white p-4 flex items-center justify-between shadow-sm shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-[#18C3D0] flex items-center justify-center text-[#075B8A] shadow-md">
                <Sparkles className="w-5 h-5 fill-current" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-extrabold text-sm tracking-wide text-white font-sans">
                    AEGIS AI
                  </h3>
                  <DataStatusIndicator compact />
                </div>
                <p className="text-[11px] text-[#A7D7E8] font-medium leading-tight">
                  Your disaster safety assistant
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() =>
                  setMessages([
                    {
                      id: 'reset-msg',
                      sender: 'bot',
                      text: 'How can I help you stay safe?',
                      timestamp: 'Just now',
                      sources: ['National Disaster Management Authority (NDMA)'],
                      safetyLevel: 'NORMAL',
                    },
                  ])
                }
                className="p-1.5 rounded-full hover:bg-white/10 text-white/70 hover:text-white transition-colors"
                title="Reset conversation"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-full hover:bg-white/10 text-white/80 hover:text-white transition-colors"
                aria-label="Close Ask AEGIS"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Context Banner */}
          <div className="bg-[#EDFAFC] px-4 py-1.5 border-b border-[#DCEBED] flex items-center justify-between text-[10px] text-[#075B8A] font-medium">
            <div className="flex items-center gap-1.5 truncate">
              <MapPin className="w-3 h-3 text-[#18C3D0] shrink-0" />
              <span className="truncate">
                Context: <strong>{weather?.cityName || 'India Region'}</strong> (Page: {activeTab.toUpperCase()})
              </span>
            </div>
            <span className="font-mono text-[#E94B68] font-bold shrink-0 ml-2">
              Risk: {selectedState?.riskScore || 72}/100
            </span>
          </div>

          {/* Messages Scroll Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-[#F4F8FA]">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-2.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.sender === 'bot' && (
                  <div className="w-7 h-7 rounded-full bg-[#075B8A] text-white flex items-center justify-center shrink-0 text-xs shadow-xs mt-0.5">
                    <Bot className="w-4 h-4 text-[#18C3D0]" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-[18px] p-3.5 text-xs leading-relaxed shadow-subtle ${
                    msg.sender === 'user'
                      ? 'bg-[#075B8A] text-white font-medium rounded-tr-xs'
                      : 'bg-white text-[#18364A] border border-[#DCEBED] rounded-tl-xs'
                  }`}
                >
                  {/* Safety level badge for bot responses */}
                  {msg.sender === 'bot' && msg.safetyLevel && msg.safetyLevel !== 'NORMAL' && (
                    <div className="mb-2 flex items-center gap-1.5">
                      <span
                        className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full uppercase inline-flex items-center gap-1 ${
                          msg.safetyLevel === 'CRITICAL'
                            ? 'bg-[#E94B68]/15 text-[#E94B68] border border-[#E94B68]/30'
                            : msg.safetyLevel === 'WARNING'
                            ? 'bg-[#F4C84A]/25 text-[#946800] border border-[#F4C84A]/40'
                            : 'bg-[#18C3D0]/20 text-[#075B8A] border border-[#18C3D0]/30'
                        }`}
                      >
                        <AlertTriangle className="w-2.5 h-2.5" />
                        {msg.safetyLevel} PROTOCOL
                      </span>
                    </div>
                  )}

                  <div className="whitespace-pre-line text-[11.5px] leading-relaxed font-normal">
                    {msg.text}
                  </div>

                  {/* Suggested Actions */}
                  {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-[#DCEBED] space-y-1.5">
                      <div className="text-[10px] font-bold text-[#708696] uppercase tracking-wider font-mono">
                        Recommended Actions:
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.suggestedActions.map((act, i) => (
                          <button
                            key={i}
                            onClick={() => handleActionClick(act)}
                            className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[10.5px] font-semibold transition-all ${
                              act.actionType === 'call'
                                ? 'bg-[#E94B68] text-white hover:bg-[#D43855] shadow-xs'
                                : 'bg-[#EDFAFC] hover:bg-[#18C3D0] text-[#075B8A] border border-[#AEEBF0]'
                            }`}
                          >
                            {act.actionType === 'call' ? (
                              <PhoneCall className="w-3 h-3" />
                            ) : (
                              <ChevronRight className="w-3 h-3 text-[#18C3D0]" />
                            )}
                            <span>{act.label}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Sources tag */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2.5 pt-1.5 border-t border-slate-100 flex items-center justify-between text-[9px] text-[#708696] font-mono">
                      <span className="truncate">
                        Source: {msg.sources[0]}
                      </span>
                      <span>{msg.timestamp}</span>
                    </div>
                  )}

                  {msg.sender === 'user' && (
                    <div className="text-[9px] mt-1 text-right font-mono text-white/70">
                      {msg.timestamp}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-2.5 items-center text-xs text-[#708696]">
                <div className="w-7 h-7 rounded-full bg-[#075B8A] text-white flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-[#18C3D0]" />
                </div>
                <div className="bg-white border border-[#DCEBED] px-3.5 py-2.5 rounded-2xl rounded-tl-xs flex items-center gap-1.5 shadow-subtle">
                  <span className="w-2 h-2 rounded-full bg-[#18C3D0] animate-bounce" />
                  <span className="w-2 h-2 rounded-full bg-[#18C3D0] animate-bounce [animation-delay:0.2s]" />
                  <span className="w-2 h-2 rounded-full bg-[#18C3D0] animate-bounce [animation-delay:0.4s]" />
                  <span className="text-[10.5px] font-medium text-[#708696] ml-1 font-mono">
                    Consulting NDMA & IMD Live Grid...
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggested Prompts Bar */}
          <div className="px-3 py-2 bg-white border-t border-[#DCEBED] overflow-x-auto no-scrollbar flex items-center gap-1.5 shrink-0">
            {SUGGESTED_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(prompt)}
                className="whitespace-nowrap text-[10.5px] font-semibold bg-[#EDFAFC] hover:bg-[#18C3D0] hover:text-[#075B8A] text-[#075B8A] px-3 py-1 rounded-full border border-[#AEEBF0] transition-colors shrink-0"
              >
                {prompt}
              </button>
            ))}
          </div>

          {/* Input Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="p-3 bg-white border-t border-[#DCEBED] flex items-center gap-2 shrink-0"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask safety protocols, flood risk, shelters..."
              className="flex-1 bg-[#F4F8FA] border border-[#DCEBED] rounded-full px-4 py-2.5 text-xs text-[#18364A] placeholder:text-[#708696] focus:outline-none focus:border-[#18C3D0] focus:ring-1 focus:ring-[#18C3D0]"
            />
            <button
              type="submit"
              disabled={!inputQuery.trim()}
              className="w-10 h-10 rounded-full bg-[#18C3D0] hover:bg-[#15B0BC] disabled:opacity-40 text-[#075B8A] flex items-center justify-center transition-all shadow-md shrink-0 active:scale-95"
              aria-label="Send message"
            >
              <Send className="w-4 h-4 fill-current" />
            </button>
          </form>
        </div>
      )}

      {/* Persistent Floating Cyan/Turquoise Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="group relative flex items-center gap-2.5 px-4.5 py-3 rounded-full bg-[#18C3D0] hover:bg-[#15B0BC] text-[#075B8A] shadow-float border-2 border-white/60 transition-all duration-200 active:scale-95 hover:shadow-xl cursor-pointer"
        aria-label="Toggle Ask AEGIS Disaster AI"
      >
        <div className="relative flex items-center justify-center">
          <MessageSquare className="w-5 h-5 text-[#075B8A] fill-current" />
          {/* Pulsing Status Dot */}
          <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#075B8A] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#075B8A]"></span>
          </span>
        </div>
        <span className="font-extrabold text-xs tracking-wider uppercase font-sans text-[#075B8A]">
          Ask AEGIS
        </span>
      </button>
    </div>
  );
};

export const FloatingAskAGIES = FloatingAskAEGIS;

