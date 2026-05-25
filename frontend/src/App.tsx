import { useRef, useState, useEffect } from 'react';
import { ChatWindow } from './components/ChatWindow';
import { ChatInput } from './components/ChatInput';
import { 
  Building2, 
  Trash2, 
  Settings, 
  Activity, 
  ShieldCheck, 
  Server, 
  HelpCircle,
  TrendingUp
} from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  team?: string;
  routing?: any;
  apiResponse?: any;
}

const DEFAULT_API_URL = 'http://127.0.0.1:8000';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef(0);
  const [apiUrl, setApiUrl] = useState(() => {
    return localStorage.getItem('sapa_api_url') || DEFAULT_API_URL;
  });
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(() => {
    return localStorage.getItem('sapa_show_tech') === 'true';
  });

  // Load chat history from LocalStorage on mount
  useEffect(() => {
    const savedHistory = localStorage.getItem('sapa_chat_history');
    if (savedHistory) {
      try {
        setMessages(JSON.parse(savedHistory));
      } catch (e) {
        console.error('Failed to parse chat history', e);
      }
    }
  }, []);

  // Save chat history to LocalStorage whenever messages change
  const saveMessages = (newMessages: Message[]) => {
    setMessages(newMessages);
    localStorage.setItem('sapa_chat_history', JSON.stringify(newMessages));
  };

  const runPrompt = async (text: string, baseMessages: Message[]) => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = activeRequestIdRef.current + 1;
    activeRequestIdRef.current = requestId;
    abortControllerRef.current = controller;

    setIsLoading(true);

    try {
      const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: text }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned status ${response.status}`);
      }

      const data = await response.json();
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.reply,
        team: data.team,
        routing: data.routing,
        apiResponse: data.api_response,
      };

      if (activeRequestIdRef.current === requestId) {
        saveMessages([...baseMessages, assistantMessage]);
      }
    } catch (error: any) {
      if (error?.name === 'AbortError') {
        if (activeRequestIdRef.current !== requestId) return;
        const stoppedMessage: Message = {
          role: 'assistant',
          content: 'Request stopped.',
        };
        saveMessages([...baseMessages, stoppedMessage]);
        return;
      }

      console.error('API Call failed:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: `**Connection or Execution Failed**\n\nCould not connect to the backend at \`${apiUrl}\`.\n\n*Error Detail:* ${error.message || 'Network unreachable'}\n\n*Solution:* Make sure your FastAPI backend is running and CORS is enabled.`,
      };
      if (activeRequestIdRef.current === requestId) {
        saveMessages([...baseMessages, errorMessage]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      if (activeRequestIdRef.current === requestId) {
        setIsLoading(false);
      }
    }
  };

  const handleSendMessage = async (text: string) => {
    if (isLoading) return;
    const userMessage: Message = { role: 'user', content: text };
    const updatedMessages = [...messages, userMessage];
    saveMessages(updatedMessages);
    await runPrompt(text, updatedMessages);
  };

  const handleEditMessage = async (index: number, text: string) => {
    if (isLoading || messages[index]?.role !== 'user') return;
    const editedMessages = [...messages.slice(0, index), { ...messages[index], content: text }];
    saveMessages(editedMessages);
    await runPrompt(text, editedMessages);
  };

  const handleRetryMessage = async (assistantIndex: number) => {
    if (isLoading) return;
    const previousUserIndex = [...messages]
      .slice(0, assistantIndex)
      .map((message, index) => ({ message, index }))
      .reverse()
      .find(({ message }) => message.role === 'user')?.index;

    if (previousUserIndex === undefined) return;
    const baseMessages = messages.slice(0, previousUserIndex + 1);
    saveMessages(baseMessages);
    await runPrompt(messages[previousUserIndex].content, baseMessages);
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  const handleClearChat = () => {
    activeRequestIdRef.current += 1;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsLoading(false);
    saveMessages([]);
  };

  // Sync settings with local storage
  const handleApiUrlChange = (val: string) => {
    setApiUrl(val);
    localStorage.setItem('sapa_api_url', val);
  };

  const handleToggleTechnical = () => {
    const newVal = !showTechnicalDetails;
    setShowTechnicalDetails(newVal);
    localStorage.setItem('sapa_show_tech', String(newVal));
  };

  return (
    <div className="app-container">
      {/* Sidebar Section */}
      <aside className="sidebar" style={styles.sidebar}>
        <div style={styles.brand}>
          <div style={styles.brandIcon}>
            <Building2 size={22} color="#06b6d4" />
          </div>
          <div>
            <h3 style={styles.brandName}>SAP B1 Agent</h3>
            <span style={styles.brandSub}>Enterprise Portal</span>
          </div>
        </div>

        <div style={styles.statusIndicator}>
          <div className="status-badge online">
            <Activity size={12} />
            <span>Shera Engine Active</span>
          </div>
        </div>

        <div style={styles.menuDivider} />

        {/* Sidebar Config Options */}
        <div style={styles.sectionHeader}>
          <Settings size={14} color="#64748b" />
          <span>Server Settings</span>
        </div>

        <div style={styles.configGroup}>
          <label style={styles.configLabel}>FastAPI Service Endpoint</label>
          <input
            type="text"
            value={apiUrl}
            onChange={(e) => handleApiUrlChange(e.target.value)}
            placeholder={DEFAULT_API_URL}
            style={styles.configInput}
          />
        </div>

        <div style={styles.configGroupInline}>
          <label style={styles.configLabel}>Show Execution Console</label>
          <input
            type="checkbox"
            checked={showTechnicalDetails}
            onChange={handleToggleTechnical}
            style={styles.checkbox}
          />
        </div>

        <div style={styles.menuDivider} />

        {/* Active Sub-Teams Summary */}
        <div style={styles.sectionHeader}>
          <ShieldCheck size={14} color="#64748b" />
          <span>Active Agent Teams</span>
        </div>

        <div style={styles.teamList}>
          <div style={styles.teamCard}>
            <div style={styles.teamHeaderRow}>
              <span className="badge badge-purchase">Purchase Team</span>
              <span style={styles.indicatorPulseBlue} />
            </div>
            <p style={styles.teamDesc}>Orchestrates POs, AP Invoices, and Vendor Returns via SAP Service Layer.</p>
          </div>

          <div style={styles.teamCard}>
            <div style={styles.teamHeaderRow}>
              <span className="badge badge-sales">Sales Team</span>
              <span style={styles.indicatorPulseGreen} />
            </div>
            <p style={styles.teamDesc}>Orchestrates Sales Orders, AR Invoices, and Customers via read-only SQL pipeline.</p>
          </div>
        </div>

        <div style={{ flex: 1 }} />

        {/* Footer Actions */}
        <div style={styles.sidebarFooter}>
          <button onClick={handleClearChat} style={styles.clearBtn}>
            <Trash2 size={14} />
            <span>Reset Workspace</span>
          </button>
        </div>
      </aside>

      {/* Main Chat Frame */}
      <main className="main-content">
        <header style={styles.appHeader}>
          <div style={styles.headerTitleGroup}>
            <Server size={18} color="#06b6d4" />
            <h2 style={styles.headerTitle}>SAP B1 ERP Supervisor Agent</h2>
          </div>
          <div style={styles.headerMetrics}>
            <div style={styles.metricItem}>
              <TrendingUp size={14} color="#34d399" />
              <span>Context: Client Local Cache</span>
            </div>
            <div style={styles.metricItemSep} />
            <div style={styles.metricItem}>
              <HelpCircle size={14} color="#94a3b8" />
              <span>Shera v1.2</span>
            </div>
          </div>
        </header>

        {/* Technical warning overlay if needed */}
        {showTechnicalDetails && (
          <div style={styles.consoleEnabledAlert}>
            <span>⚡ DevConsole mode enabled: Inspector logs and compiled SQL blocks will render in the conversation.</span>
          </div>
        )}

        {/* Dynamic chat lists */}
        <ChatWindow 
          messages={messages} 
          onSuggestionClick={handleSendMessage} 
          onEditMessage={handleEditMessage}
          onRetryMessage={handleRetryMessage}
          isLoading={isLoading} 
        />

        {/* Footer Prompt Input */}
        <div style={styles.inputArea}>
          <ChatInput onSendMessage={handleSendMessage} onStop={handleStop} isLoading={isLoading} />
        </div>
      </main>
    </div>
  );
}

// Styling parameters for modern premium enterprise look
const styles: { [key: string]: React.CSSProperties } = {
  sidebar: {
    height: '100%',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '1.25rem',
  },
  brandIcon: {
    width: '40px',
    height: '40px',
    borderRadius: '10px',
    background: '#06b6d41a',
    border: '1px solid #06b6d433',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  brandName: {
    color: '#fff',
    fontSize: '0.975rem',
    fontWeight: 700,
    margin: 0,
    letterSpacing: '0.25px',
  },
  brandSub: {
    color: '#64748b',
    fontSize: '0.75rem',
    fontWeight: 500,
  },
  statusIndicator: {
    marginBottom: '1.5rem',
  },
  menuDivider: {
    height: '1px',
    background: '#1e293b55',
    margin: '1rem 0',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '0.725rem',
    fontWeight: 700,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: '0.75px',
    marginBottom: '0.75rem',
  },
  configGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    marginBottom: '1rem',
  },
  configGroupInline: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '0.75rem',
  },
  configLabel: {
    fontSize: '0.775rem',
    color: '#cbd5e1',
    fontWeight: 500,
  },
  configInput: {
    background: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '6px 10px',
    fontSize: '0.8rem',
    color: '#cbd5e1',
  },
  checkbox: {
    width: '15px',
    height: '15px',
    cursor: 'pointer',
  },
  teamList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  teamCard: {
    background: '#090d1655',
    border: '1px solid #1e293b55',
    borderRadius: '8px',
    padding: '10px 12px',
  },
  teamHeaderRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '6px',
  },
  teamDesc: {
    fontSize: '0.725rem',
    color: '#64748b',
    margin: 0,
    lineHeight: 1.4,
  },
  indicatorPulseBlue: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#3b82f6',
    boxShadow: '0 0 8px #3b82f6',
  },
  indicatorPulseGreen: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#10b981',
    boxShadow: '0 0 8px #10b981',
  },
  sidebarFooter: {
    paddingTop: '1rem',
    borderTop: '1px solid #1e293b55',
  },
  clearBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    width: '100%',
    background: '#ef444415',
    border: '1px solid #ef444433',
    color: '#f87171',
    borderRadius: '8px',
    padding: '8px 12px',
    fontSize: '0.825rem',
    fontWeight: 600,
    transition: 'all 0.15s ease',
  },
  appHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1rem 1.5rem',
    background: '#0b1533',
    borderBottom: '1px solid #1e293b',
    flexShrink: 0,
  },
  headerTitleGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  headerTitle: {
    margin: 0,
    fontSize: '1rem',
    fontWeight: 700,
    color: '#fff',
  },
  headerMetrics: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  metricItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '0.775rem',
    color: '#94a3b8',
    fontWeight: 500,
  },
  metricItemSep: {
    width: '1px',
    height: '12px',
    background: '#1e293b',
  },
  consoleEnabledAlert: {
    background: '#0e749015',
    borderBottom: '1px solid #0891b233',
    color: '#22d3ee',
    fontSize: '0.75rem',
    fontWeight: 500,
    padding: '6px 1.5rem',
    display: 'flex',
    alignItems: 'center',
  },
  inputArea: {
    padding: '0 1.5rem 1.5rem 1.5rem',
    background: 'transparent',
    flexShrink: 0,
  },
};

export default App;
