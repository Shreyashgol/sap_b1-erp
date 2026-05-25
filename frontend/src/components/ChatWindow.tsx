import React, { useRef, useEffect, useState } from 'react';
import { Bot, User, CornerDownRight, Copy, RotateCcw, Pencil, Check, X } from 'lucide-react';
import { DataChart } from './DataChart';
import { DetailsInspector } from './DetailsInspector';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  team?: string;
  routing?: any;
  apiResponse?: any;
}

interface ChatWindowProps {
  messages: Message[];
  onSuggestionClick: (suggestion: string) => void;
  onEditMessage: (index: number, message: string) => void;
  onRetryMessage: (index: number) => void;
  isLoading: boolean;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  onSuggestionClick,
  onEditMessage,
  onRetryMessage,
  isLoading,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const parseMessage = (text: string) => {
    // Split message into main body and suggestion links
    const suggestionHeaderRegex = /\*\*(?:You can ask next|Suggested Questions|Suggestions):\*\*|You can ask next:/i;
    const parts = text.split(suggestionHeaderRegex);
    const mainBody = parts[0].trim();
    const suggestionsPart = parts[1] || '';

    const suggestions = suggestionsPart
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('-') || line.startsWith('*'))
      .map((line) => line.replace(/^[-*]\s*/, '').trim());

    return { mainBody, suggestions };
  };

  const beginEdit = (index: number, content: string) => {
    setEditingIndex(index);
    setEditingText(content);
  };

  const cancelEdit = () => {
    setEditingIndex(null);
    setEditingText('');
  };

  const submitEdit = (index: number) => {
    const nextText = editingText.trim();
    if (!nextText) return;
    cancelEdit();
    onEditMessage(index, nextText);
  };

  const copyMessage = async (index: number, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedIndex(index);
      window.setTimeout(() => setCopiedIndex(null), 1400);
    } catch {
      setCopiedIndex(null);
    }
  };

  const renderLine = (line: string, idx: number) => {
    let trimmed = line.trim();
    if (!trimmed) return <div key={idx} style={{ height: '0.5rem' }} />;

    // Header Check
    if (trimmed.startsWith('###')) {
      return (
        <h4 key={idx} style={styles.header3}>
          {trimmed.substring(3).trim()}
        </h4>
      );
    }
    if (trimmed.startsWith('##')) {
      return (
        <h3 key={idx} style={styles.header2}>
          {trimmed.substring(2).trim()}
        </h3>
      );
    }

    // Check for List Bullet
    const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
    if (isBullet) {
      trimmed = trimmed.substring(2).trim();
    }

    // Process bold/inline code formatting
    const elements: React.ReactNode[] = [];
    let currentString = trimmed;
    let safetyCounter = 0;

    while (currentString.length > 0 && safetyCounter < 50) {
      safetyCounter++;
      const boldIndex = currentString.indexOf('**');
      const codeIndex = currentString.indexOf('`');

      if (boldIndex === -1 && codeIndex === -1) {
        elements.push(currentString);
        break;
      }

      // Determine which format marker occurs first
      if (boldIndex !== -1 && (codeIndex === -1 || boldIndex < codeIndex)) {
        if (boldIndex > 0) {
          elements.push(currentString.substring(0, boldIndex));
        }
        const nextBold = currentString.indexOf('**', boldIndex + 2);
        if (nextBold !== -1) {
          const boldText = currentString.substring(boldIndex + 2, nextBold);
          elements.push(<strong key={safetyCounter} style={styles.strongText}>{boldText}</strong>);
          currentString = currentString.substring(nextBold + 2);
        } else {
          elements.push(currentString.substring(boldIndex));
          break;
        }
      } else {
        if (codeIndex > 0) {
          elements.push(currentString.substring(0, codeIndex));
        }
        const nextCode = currentString.indexOf('`', codeIndex + 1);
        if (nextCode !== -1) {
          const codeText = currentString.substring(codeIndex + 1, nextCode);
          elements.push(<code key={safetyCounter} style={styles.codeText}>{codeText}</code>);
          currentString = currentString.substring(nextCode + 1);
        } else {
          elements.push(currentString.substring(codeIndex));
          break;
        }
      }
    }

    if (isBullet) {
      return (
        <div key={idx} style={styles.listItem}>
          <span style={styles.bulletSymbol}>•</span>
          <div>{elements}</div>
        </div>
      );
    }

    return <p key={idx} style={styles.paragraph}>{elements}</p>;
  };

  const renderContentText = (text: string) => {
    const lines = text.split('\n');
    const renderedElements: React.ReactNode[] = [];
    
    let inTable = false;
    let tableHeaders: string[] = [];
    let tableRows: string[][] = [];

    const flushTable = (key: number) => {
      if (tableHeaders.length > 0 || tableRows.length > 0) {
        renderedElements.push(
          <div key={`table-wrapper-${key}`} style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {tableHeaders.map((h, i) => (
                    <th key={i} style={styles.tableHeader}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, rowIndex) => (
                  <tr key={rowIndex} style={rowIndex % 2 === 0 ? styles.tableRowEven : styles.tableRowOdd}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} style={styles.tableCell}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableHeaders = [];
        tableRows = [];
      }
      inTable = false;
    };

    for (let idx = 0; idx < lines.length; idx++) {
      const line = lines[idx].trim();
      
      // Check if it's a table row
      if (line.startsWith('|') && line.endsWith('|')) {
        const parts = line
          .split('|')
          .map(p => p.trim())
          .filter((_, i, arr) => i > 0 && i < arr.length - 1);
        
        // Separator row check e.g. |---|---|
        const isSeparator = parts.length > 0 && parts.every(p => p.startsWith('-') || p.includes('---'));
        
        if (isSeparator) {
          inTable = true;
          continue;
        }
        
        if (!inTable) {
          // This is the header row
          tableHeaders = parts;
          inTable = true;
        } else {
          // This is a normal body row
          tableRows.push(parts);
        }
      } else {
        if (inTable) {
          flushTable(idx);
        }
        renderedElements.push(renderLine(line, idx));
      }
    }
    
    if (inTable) {
      flushTable(lines.length);
    }
    
    return renderedElements;
  };

  return (
    <div style={styles.windowContainer}>
      {messages.length === 0 ? (
        <div style={styles.emptyContainer}>
          <div style={styles.welcomeCircle}>
            <Bot size={48} color="#06b6d4" />
          </div>
          <h2 style={styles.welcomeTitle}>Welcome, I'm Shera</h2>
          <p style={styles.welcomeSubtitle}>
            Your agentic interface for SAP Business One ERP. I can search records, create documents, cancel transactions, and visualize charts.
          </p>
          <div style={styles.welcomeSuggestions}>
            <h5 style={styles.suggestionsHeader}>Try asking:</h5>
            <div style={styles.welcomePills}>
              {[
                'Show top 5 sales orders',
                'Show overdue purchase orders',
                'Chart monthly revenue invoice trends',
                'What is the total AP invoice balance due?',
              ].map((pill, i) => (
                <button
                  key={i}
                  onClick={() => onSuggestionClick(pill)}
                  style={styles.welcomePill}
                >
                  <CornerDownRight size={12} color="#06b6d4" />
                  <span>{pill}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div style={styles.chatList}>
          {messages.map((message, index) => {
            const isUser = message.role === 'user';
            const { mainBody, suggestions } = isUser
              ? { mainBody: message.content, suggestions: [] }
              : parseMessage(message.content);

            return (
              <div
                key={index}
                style={{
                  ...styles.chatRow,
                  flexDirection: isUser ? 'row-reverse' : 'row',
                }}
              >
                <div
                  style={{
                    ...styles.avatar,
                    backgroundColor: isUser ? '#1e40af' : '#0f1c3f',
                    borderColor: isUser ? '#3b82f6' : '#1e293b',
                  }}
                >
                  {isUser ? (
                    <User size={16} color="#93c5fd" />
                  ) : (
                    <Bot size={16} color="#06b6d4" />
                  )}
                </div>

                <div style={{ ...styles.bubbleWrapper, alignItems: isUser ? 'flex-end' : 'flex-start' }}>
                  {/* Bubble content */}
                  <div
                    style={{
                      ...styles.bubble,
                      backgroundColor: isUser ? 'var(--color-user-bubble)' : 'var(--color-agent-bubble)',
                      borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                    }}
                  >
                    {editingIndex === index ? (
                      <div style={styles.editBox}>
                        <textarea
                          value={editingText}
                          onChange={(event) => setEditingText(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' && !event.shiftKey) {
                              event.preventDefault();
                              submitEdit(index);
                            }
                            if (event.key === 'Escape') {
                              cancelEdit();
                            }
                          }}
                          style={styles.editTextarea}
                          autoFocus
                        />
                        <div style={styles.editActions}>
                          <button type="button" onClick={cancelEdit} style={styles.iconTextButton}>
                            <X size={14} />
                            <span>Cancel</span>
                          </button>
                          <button type="button" onClick={() => submitEdit(index)} style={styles.primaryTextButton}>
                            <Check size={14} />
                            <span>Send</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      renderContentText(mainBody)
                    )}
                  </div>

                  {editingIndex !== index && (
                    <div style={{ ...styles.messageActions, justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
                      {isUser ? (
                        <button
                          type="button"
                          onClick={() => beginEdit(index, message.content)}
                          disabled={isLoading}
                          title="Edit message"
                          style={{ ...styles.iconButton, ...(isLoading ? styles.iconButtonDisabled : {}) }}
                        >
                          <Pencil size={14} />
                        </button>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => copyMessage(index, message.content)}
                            title="Copy response"
                            style={styles.iconButton}
                          >
                            <Copy size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => onRetryMessage(index)}
                            disabled={isLoading}
                            title="Retry response"
                            style={{ ...styles.iconButton, ...(isLoading ? styles.iconButtonDisabled : {}) }}
                          >
                            <RotateCcw size={14} />
                          </button>
                          {copiedIndex === index && <span style={styles.copiedText}>Copied</span>}
                        </>
                      )}
                    </div>
                  )}

                  {/* Suggestions list (Only for assistant messages, render pills if present) */}
                  {!isUser && suggestions.length > 0 && (
                    <div style={styles.suggestionsContainer}>
                      <span style={styles.suggestionsLabel}>Follow-up actions:</span>
                      <div style={styles.suggestionsList}>
                        {suggestions.map((suggestion, i) => (
                          <button
                            key={i}
                            onClick={() => onSuggestionClick(suggestion)}
                            style={styles.suggestionPill}
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Rendering SVG Chart if applicable */}
                  {!isUser && (
                    <DataChart prompt={messages[index - 1]?.content || ''} apiResponse={message.apiResponse} />
                  )}

                  {/* Rendering Technical Details console */}
                  {!isUser && (
                    <DetailsInspector
                      routing={message.routing}
                      apiResponse={message.apiResponse}
                      team={message.team || 'purchase'}
                    />
                  )}
                </div>
              </div>
            );
          })}

          {isLoading && (
            <div style={styles.chatRow}>
              <div style={{ ...styles.avatar, backgroundColor: '#0f1c3f', borderColor: '#1e293b' }}>
                <Bot size={16} color="#06b6d4" />
              </div>
              <div style={styles.bubbleWrapper}>
                <div style={{ ...styles.bubble, backgroundColor: 'var(--color-agent-bubble)' }}>
                  <div style={styles.typingContainer}>
                    <div className="dot" style={styles.dot} />
                    <div className="dot" style={{ ...styles.dot, animationDelay: '0.2s' }} />
                    <div className="dot" style={{ ...styles.dot, animationDelay: '0.4s' }} />
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
};

// Styling definitions
const styles: { [key: string]: React.CSSProperties } = {
  windowContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '1.5rem',
    display: 'flex',
    flexDirection: 'column',
  },
  emptyContainer: {
    margin: 'auto',
    maxWidth: '540px',
    textAlign: 'center',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '2rem 1.5rem',
  },
  welcomeCircle: {
    width: '80px',
    height: '80px',
    borderRadius: '50%',
    background: '#06b6d41a',
    border: '2px solid #06b6d433',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '1.25rem',
    animation: 'pulseBorder 2.5s infinite',
  },
  welcomeTitle: {
    fontSize: '1.75rem',
    fontWeight: 700,
    color: '#fff',
    marginBottom: '0.5rem',
  },
  welcomeSubtitle: {
    color: '#94a3b8',
    fontSize: '0.95rem',
    lineHeight: 1.6,
    marginBottom: '2rem',
  },
  welcomeSuggestions: {
    width: '100%',
    textAlign: 'left',
  },
  suggestionsHeader: {
    color: '#cbd5e1',
    marginBottom: '0.75rem',
    fontSize: '0.85rem',
    fontWeight: 600,
  },
  welcomePills: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  welcomePill: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    background: '#0f1c3f',
    border: '1px solid #1e293b',
    borderRadius: '8px',
    padding: '10px 14px',
    color: '#cbd5e1',
    textAlign: 'left',
    fontSize: '0.85rem',
    width: '100%',
  },
  chatList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.5rem',
  },
  chatRow: {
    display: 'flex',
    gap: '12px',
    maxWidth: '850px',
    width: '100%',
    alignSelf: 'center',
    animation: 'fadeInUp 0.25s ease-out',
  },
  avatar: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    border: '1px solid',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: '4px',
  },
  bubbleWrapper: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    maxWidth: 'calc(100% - 44px)',
  },
  bubble: {
    padding: '0.875rem 1.125rem',
    color: '#cbd5e1',
    fontSize: '0.925rem',
    lineHeight: 1.6,
    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
  },
  messageActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    marginTop: '6px',
    minHeight: '28px',
  },
  iconButton: {
    width: '28px',
    height: '28px',
    borderRadius: '8px',
    border: '1px solid #1e293b',
    background: '#0b1533',
    color: '#94a3b8',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconButtonDisabled: {
    cursor: 'not-allowed',
    opacity: 0.45,
  },
  copiedText: {
    color: '#94a3b8',
    fontSize: '0.75rem',
    fontWeight: 600,
  },
  editBox: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  editTextarea: {
    minHeight: '88px',
    background: '#081225',
    color: '#f8fafc',
    border: '1px solid #334155',
    borderRadius: '8px',
    resize: 'vertical',
    lineHeight: 1.5,
    fontFamily: 'inherit',
    fontSize: '0.925rem',
  },
  editActions: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: '8px',
  },
  iconTextButton: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    color: '#cbd5e1',
    background: '#0b1533',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '6px 10px',
    fontSize: '0.8rem',
    fontWeight: 600,
  },
  primaryTextButton: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    color: '#fff',
    background: '#2563eb',
    border: '1px solid #3b82f6',
    borderRadius: '8px',
    padding: '6px 10px',
    fontSize: '0.8rem',
    fontWeight: 700,
  },
  paragraph: {
    margin: '0 0 0.75rem 0',
  },
  header2: {
    fontSize: '1.25rem',
    color: '#fff',
    margin: '1rem 0 0.5rem 0',
  },
  header3: {
    fontSize: '1.05rem',
    color: '#fff',
    margin: '0.75rem 0 0.4rem 0',
  },
  strongText: {
    color: '#fff',
    fontWeight: 600,
  },
  codeText: {
    color: '#f43f5e',
    background: '#88133722',
    padding: '1px 5px',
    borderRadius: '4px',
    fontFamily: 'monospace',
  },
  listItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    margin: '0 0 0.5rem 0.5rem',
  },
  bulletSymbol: {
    color: '#06b6d4',
    fontSize: '1.1rem',
    lineHeight: '1.1',
  },
  suggestionsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    marginTop: '0.75rem',
  },
  suggestionsLabel: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  suggestionsList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
  },
  suggestionPill: {
    background: '#0f1c3f',
    border: '1px solid #1e293b',
    color: '#38bdf8',
    padding: '5px 10px',
    borderRadius: '999px',
    fontSize: '0.8rem',
    fontWeight: 500,
    transition: 'all 0.15s ease',
  },
  typingContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 0',
  },
  dot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#06b6d4',
    animation: 'pulseBorder 1.2s infinite ease-in-out',
  },
  tableWrapper: {
    overflowX: 'auto',
    margin: '1rem 0',
    borderRadius: '8px',
    border: '1px solid #1e293b',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '0.85rem',
    textAlign: 'left',
    background: '#090f20',
  },
  tableHeader: {
    background: '#0f1c3f',
    color: '#38bdf8',
    fontWeight: 600,
    padding: '10px 14px',
    borderBottom: '2px solid #1e293b',
  },
  tableRowEven: {
    background: '#0d1630',
    borderBottom: '1px solid #1e293b55',
  },
  tableRowOdd: {
    background: '#090f20',
    borderBottom: '1px solid #1e293b55',
  },
  tableCell: {
    padding: '10px 14px',
    color: '#cbd5e1',
  },
};
