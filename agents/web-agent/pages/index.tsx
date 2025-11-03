import React, { useState } from 'react';
import axios from 'axios';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    setLoading(true);
    setResponse(null);
    try {
      const res = await axios.post('/api/agent', { prompt });
      setResponse(res.data);
    } catch (err: any) {
      setResponse({ error: err.message });
    }
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 600, margin: '40px auto', padding: 24, border: '1px solid #eee', borderRadius: 8 }}>
      <h2>DevOps Nexus Web Agent</h2>
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        rows={4}
        style={{ width: '100%', marginBottom: 12 }}
        placeholder="Enter your prompt here..."
      />
      <button onClick={handleSend} disabled={loading || !prompt} style={{ padding: '8px 24px' }}>
        {loading ? 'Sending...' : 'Send'}
      </button>
      {response && (
        <div style={{ marginTop: 24 }}>
          <h4>LLM Response:</h4>
          <pre>{response.llmResponse}</pre>
          <h4>MCP Result:</h4>
          <pre>{response.mcpResult}</pre>
          {response.error && <div style={{ color: 'red' }}>{response.error}</div>}
        </div>
      )}
    </div>
  );
}
