import ReactMarkdown from 'react-markdown';

const MarkdownRenderer: React.FC<{ content: string; className?: string }> = ({ content, className = '' }) => {
  return (
    <div className={className} style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: '1.6' }}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--ink)', margin: '8px 0 6px' }}>{children}</h1>,
          h2: ({ children }) => <h2 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--ink)', margin: '8px 0 4px' }}>{children}</h2>,
          h3: ({ children }) => <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--ink)', margin: '6px 0 3px' }}>{children}</h3>,
          h4: ({ children }) => <h4 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--ink2)', margin: '6px 0 3px' }}>{children}</h4>,
          p: ({ children }) => <p style={{ marginBottom: '6px', lineHeight: '1.6' }}>{children}</p>,
          ul: ({ children }) => <ul style={{ listStyle: 'disc', paddingLeft: '16px', marginBottom: '6px' }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ listStyle: 'decimal', paddingLeft: '16px', marginBottom: '6px' }}>{children}</ol>,
          li: ({ children }) => <li style={{ lineHeight: '1.6' }}>{children}</li>,
          strong: ({ children }) => <strong style={{ fontWeight: 700, color: 'var(--ink)' }}>{children}</strong>,
          em: ({ children }) => <em style={{ fontStyle: 'italic', color: 'var(--ink2)' }}>{children}</em>,
          blockquote: ({ children }) => (
            <blockquote style={{ borderLeft: '2px solid var(--line)', paddingLeft: '10px', margin: '6px 0', color: 'var(--ink2)', fontStyle: 'italic' }}>{children}</blockquote>
          ),
          code: ({ children, className: codeClassName }) => {
            const isBlock = codeClassName?.includes('language-');
            if (isBlock) {
              return (
                <pre style={{ background: 'var(--cream)', borderRadius: '3px', padding: '6px 8px', margin: '6px 0', overflowX: 'auto', fontSize: '10px' }}>
                  <code>{children}</code>
                </pre>
              );
            }
            return <code style={{ background: 'var(--cream)', padding: '1px 4px', borderRadius: '2px', fontSize: '10px', color: 'var(--orange)' }}>{children}</code>;
          },
          pre: ({ children }) => <pre style={{ background: 'var(--cream)', borderRadius: '3px', padding: '6px 8px', margin: '6px 0', overflowX: 'auto' }}>{children}</pre>,
          a: ({ children, href }) => <a href={href} style={{ color: 'var(--blue)', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer">{children}</a>,
          hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--line)', margin: '8px 0' }} />,
          table: ({ children }) => <table style={{ width: '100%', margin: '6px 0', borderCollapse: 'collapse' }}>{children}</table>,
          th: ({ children }) => <th style={{ border: '1px solid var(--line)', padding: '4px 8px', textAlign: 'left', fontWeight: 600, background: 'var(--cream)' }}>{children}</th>,
          td: ({ children }) => <td style={{ border: '1px solid var(--line)', padding: '4px 8px' }}>{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;
