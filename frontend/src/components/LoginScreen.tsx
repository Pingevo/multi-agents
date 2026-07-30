import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export function LoginScreen() {
  const { getLoginUrl } = useAuth();
  const [oauthUrl, setOauthUrl] = useState('');

  useEffect(() => {
    getLoginUrl().then((url) => {
      if (url) setOauthUrl(url);
    });
  }, [getLoginUrl]);

  const handleOAuthLogin = () => {
    if (oauthUrl) {
      try {
        const url = new URL(oauthUrl);
        url.searchParams.set('redirect_uri', window.location.origin + '/');
        window.location.href = url.toString();
      } catch {
        window.location.href = oauthUrl;
      }
    } else {
      const params = new URLSearchParams({
        app_name: 'Multi-Agent Platform',
        redirect_uri: window.location.origin + '/',
        client_id: 'multi_agent_app',
      });
      window.location.href = 'https://data.digital.in.th/system81/login?' + params.toString();
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#e8dcc8' }}>
      <div className="w-full max-w-md p-6 bg-paper border border-line-2 rounded-retro shadow-retro-lg">
        <div className="text-center mb-6">
          <div className="text-4xl mb-2">🪟</div>
          <h1 className="text-xl font-bold text-ink mb-1">Agent OS</h1>
          <p className="text-[12px] text-ink-3">Sign in to access your workspace</p>
        </div>

        <button
          type="button"
          onClick={handleOAuthLogin}
          className="w-full py-2.5 px-4 bg-green border border-green text-white font-bold rounded-retro hover:bg-green-light transition-colors text-[13px]"
        >
          Login with System81
        </button>
      </div>
    </div>
  );
}
