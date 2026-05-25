import React, { useState, useRef, useEffect } from 'react';
import { Send, CornerDownLeft } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, isLoading }) => {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim() && !isLoading) {
      onSendMessage(text.trim());
      setText('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form style={styles.inputContainer} onSubmit={handleSubmit}>
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask Shera anything: e.g. Show top 5 sales orders | Show overdue purchase orders"
        style={styles.textarea}
        disabled={isLoading}
      />
      <div style={styles.actionRow}>
        <div style={styles.metaHint}>
          <CornerDownLeft size={12} color="#475569" />
          <span>Press Enter to send</span>
        </div>
        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          style={{
            ...styles.sendButton,
            ...(!text.trim() || isLoading ? styles.sendButtonDisabled : {}),
          }}
        >
          <Send size={16} />
          <span>{isLoading ? 'Processing...' : 'Send'}</span>
        </button>
      </div>
    </form>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  inputContainer: {
    background: '#0f1c3f',
    border: '1px solid #1e293b',
    borderRadius: '12px',
    padding: '0.75rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    boxShadow: '0 -4px 20px rgba(0, 0, 0, 0.15)',
  },
  textarea: {
    background: 'transparent',
    border: 'none',
    color: '#f8fafc',
    fontSize: '0.925rem',
    resize: 'none',
    width: '100%',
    maxHeight: '160px',
    outline: 'none',
    padding: '4px',
    fontFamily: 'inherit',
    boxSizing: 'border-box',
  },
  actionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTop: '1px solid #1e293b55',
    paddingTop: '6px',
  },
  metaHint: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '0.75rem',
    color: '#64748b',
  },
  sendButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    backgroundColor: '#3b82f6',
    color: '#fff',
    padding: '6px 14px',
    borderRadius: '8px',
    fontSize: '0.85rem',
    fontWeight: 600,
    boxShadow: '0 2px 8px rgba(59, 130, 246, 0.3)',
  },
  sendButtonDisabled: {
    backgroundColor: '#1e293b',
    color: '#64748b',
    boxShadow: 'none',
    cursor: 'not-allowed',
  },
};
