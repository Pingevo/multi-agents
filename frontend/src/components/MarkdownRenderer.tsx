import ReactMarkdown from 'react-markdown';

const MarkdownRenderer: React.FC<{ content: string; className?: string }> = ({ content, className = '' }) => {
  return (
    <div className={`text-xs text-text leading-relaxed ${className}`}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="text-base font-bold text-text mt-3 mb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-sm font-bold text-text mt-3 mb-1.5">{children}</h2>,
          h3: ({ children }) => <h3 className="text-xs font-bold text-text mt-2 mb-1">{children}</h3>,
          h4: ({ children }) => <h4 className="text-xs font-semibold text-text mt-2 mb-1">{children}</h4>,
          p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => <strong className="font-bold text-text">{children}</strong>,
          em: ({ children }) => <em className="italic text-text-2">{children}</em>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-border pl-3 my-2 text-text-2 italic">{children}</blockquote>
          ),
          code: ({ children, className: codeClassName }) => {
            const isBlock = codeClassName?.includes('language-');
            if (isBlock) {
              return (
                <pre className="bg-surface-3 rounded-md p-2 my-2 overflow-x-auto text-[10px]">
                  <code>{children}</code>
                </pre>
              );
            }
            return <code className="bg-surface-3 px-1 py-0.5 rounded text-[10px] text-accent">{children}</code>;
          },
          pre: ({ children }) => <pre className="bg-surface-3 rounded-md p-2 my-2 overflow-x-auto">{children}</pre>,
          a: ({ children, href }) => <a href={href} className="text-accent underline hover:text-accent/80" target="_blank" rel="noopener noreferrer">{children}</a>,
          hr: () => <hr className="border-border my-3" />,
          table: ({ children }) => <table className="w-full my-2 border-collapse">{children}</table>,
          th: ({ children }) => <th className="border border-border px-2 py-1 text-left font-semibold bg-surface-2">{children}</th>,
          td: ({ children }) => <td className="border border-border px-2 py-1">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;
