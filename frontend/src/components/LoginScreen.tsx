import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export function LoginScreen() {
  const { login, getLoginUrl } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [oauthUrl, setOauthUrl] = useState('');

  useEffect(() => {
    getLoginUrl().then((url) => {
      if (url) setOauthUrl(url);
    });
  }, [getLoginUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) {
      setError('Please enter a username');
      return;
    }
    if (!password) {
      setError('Please enter a password');
      return;
    }
    setLoading(true);
    setError('');
    const result = await login(username.trim(), password);
    if (!result.success) {
      setError(result.error || 'Login failed');
    }
    setLoading(false);
  };

  const handleOAuthLogin = () => {
    if (oauthUrl) {
      // Replace redirect_uri in the URL to point back to frontend
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
          disabled={loading}
          className="w-full py-2.5 px-4 mb-4 bg-green border border-green text-white font-bold rounded-retro hover:bg-green-light disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-[13px]"
        >
          Login with System81
        </button>

        <div className="border-t border-line my-4" />

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label htmlFor="username" className="block text-[11px] font-semibold text-ink-2 mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              disabled={loading}
              className="w-full px-3 py-2 bg-paper border border-line-2 rounded-retro-sm text-ink text-[13px] placeholder-ink-3 focus:outline-none focus:border-orange transition-colors"
              autoFocus
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-[11px] font-semibold text-ink-2 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              disabled={loading}
              className="w-full px-3 py-2 bg-paper border border-line-2 rounded-retro-sm text-ink text-[13px] placeholder-ink-3 focus:outline-none focus:border-orange transition-colors"
            />
          </div>

          {error && (
            <div className="text-[11px] text-red bg-red/10 border border-red/30 rounded-retro-sm px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            className="w-full py-2.5 px-4 bg-orange border border-orange text-white font-bold rounded-retro hover:bg-orange-light disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-[13px]"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
