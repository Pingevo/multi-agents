import { useState, useRef } from 'react';
import { Send, Terminal } from 'lucide-react';

interface CommandConsoleProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export const CommandConsole: React.FC<CommandConsoleProps> = ({ onSend, disabled }) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  return (
    <div className="bg-surface border-t border-border flex items-end px-4 py-2 gap-3 shrink-0">
      <Terminal className="w-4 h-4 text-text-2 mb-2.5" />
      <div className="flex-1 flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? 'Waiting for action...' : 'Type a message... (Enter to send, Shift+Enter for new line)'}
          disabled={disabled}
          rows={1}
          className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-2 focus:outline-none focus:border-accent disabled:opacity-50 resize-none overflow-hidden"
          style={{ minHeight: '38px', maxHeight: '120px' }}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !input.trim()}
          className="p-2 rounded-lg bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors mb-0.5"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
