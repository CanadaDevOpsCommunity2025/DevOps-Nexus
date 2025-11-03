import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';
import dotenv from 'dotenv';
dotenv.config();

const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

// Tool/function definition for Gemini (mirrors MCP server's cherry-pick tool)
const geminiTools = [
  {
    function_declarations: [
      {
        name: "cherry-pick",
        description: "Cherry-pick commits from PRs based on a filter query to a target branch",
        parameters: {
          type: "object",
          properties: {
            repository: { type: "string", description: "Repository name" },
            targetBranch: { type: "string", description: "Target branch for cherry-pick" },
            prFilterQuery: { type: "string", description: "Pull request filter query" },
            callbackUrl: { type: "string", description: "Optional callback URL" },
          },
          required: ["repository", "targetBranch", "prFilterQuery"],
        },
      },
    ],
  },
];

// This is a placeholder for the LLM and MCP server integration
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { prompt } = req.body;
  if (!prompt) {
    return res.status(400).json({ error: 'Prompt is required' });
  }

  if (!GEMINI_API_KEY) {
    return res.status(500).json({ error: 'Gemini API key not configured in environment.' });
  }

  let llmResponse = '';
  let geminiRaw = null;
  let toolCallResult = null;
  try {
    // Call Gemini with tool/function definitions
    const geminiRes = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [
          {
            parts: [
              { text: prompt }
            ]
          }
        ],
        tools: geminiTools
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    geminiRaw = geminiRes.data;
    // If Gemini returns a function call, handle it
    const candidate = geminiRaw?.candidates?.[0];
  const toolCall = candidate?.content?.parts?.find((p: any) => p && (p as any).functionCall)?.functionCall as { name: string; args: any } | undefined;

    console.log('Gemini raw response:', JSON.stringify(geminiRaw));
    if (toolCall) {
      // Extract function name and arguments
      const { name, args } = toolCall;
      console.log(`Gemini requested tool call: ${name} with args: ${JSON.stringify(args)}`);
      toolCallResult = await callMcpServerTool(name, args);
      llmResponse = `Tool call result: ${JSON.stringify(toolCallResult)}`;
    } else {
      // Try to extract the text from all possible locations
      console.log('No tool call requested by Gemini.');
      const parts = candidate?.content?.parts;
      if (Array.isArray(parts) && parts.length > 0 && parts[0]?.text) {
        llmResponse = parts[0].text;
      } else if (candidate?.content?.text) {
        llmResponse = candidate.content.text;
      } else {
        llmResponse = JSON.stringify(candidate);
      }
    }
  } catch (err: any) {
    let safeDetails: any = err?.response?.data || err.message;
    if (safeDetails && typeof safeDetails === 'object') {
      try {
        const seen = new WeakSet();
        safeDetails = JSON.parse(JSON.stringify(safeDetails, (_k, v) => {
          if (typeof v === 'object' && v !== null) {
            if (seen.has(v)) return '[Circular]';
            seen.add(v);
          }
          return v;
        }));
      } catch {
        safeDetails = '[Unserializable error object]';
      }
    }
    console.error('Gemini API error:', safeDetails);
    return res.status(500).json({ error: 'Gemini API error', details: safeDetails });
  }

  async function callMcpServerTool(name: string, args: any) {
    // The MCP server should be running and accessible via HTTP SSE endpoint
    // Example: http://localhost:8080/mcp/sse
    const sseUrl = process.env.MCP_SSE_URL || 'http://localhost:8080/mcp/sse';
    const rpcReq = {
      jsonrpc: "2.0",
      id: 1,
      method: "callTool",
      params: {
        name,
        arguments: args
      }
    };

    // We'll POST the request and listen for SSE events (using EventSource polyfill for Node)
    // For simplicity, we'll POST and then collect the response (since native SSE in Node is non-trivial)
    // In production, use a proper SSE client or library

    // Send the tool call request
    const axiosRes = await axios.post(sseUrl, rpcReq, {
      headers: { 'Content-Type': 'application/json' },
      responseType: 'stream',
      // Give the stream enough time; we'll close early once we have first event
      timeout: 60000
    });

    console.log(`MCP server responded with status: ${axiosRes.status}`);
    return new Promise((resolve, reject) => {
      let buffer = '';
      let resolved = false;
      const stream = axiosRes.data;

      const finishWith = (raw: string) => {
        if (resolved) return;
        resolved = true;
        try {
          const segments = raw.split(/\n\n+/).map(s => s.trim()).filter(Boolean);
          const firstData = segments.find(seg => seg.startsWith('data:'));
          if (!firstData) return resolve(raw);
          const payload = firstData.replace(/^data:\s*/, '');
          resolve(JSON.parse(payload));
        } catch (e) {
          resolve(raw);
        }
        // Destroy stream to prevent lingering open connection / abort
        if (stream.destroy) stream.destroy();
      };

      stream.on('data', (chunk: Buffer) => {
        buffer += chunk.toString();
        // Resolve immediately upon first data event
        finishWith(buffer);
      });
      stream.on('end', () => {
        finishWith(buffer);
      });
      stream.on('error', (err: any) => {
        if (resolved) return;
        resolved = true;
        reject(err);
      });
      // Safety timeout in case no data arrives (should be earlier than axios timeout)
      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          if (stream.destroy) stream.destroy();
          resolve('[MCP tool call timeout waiting for SSE data]');
        }
      }, 10000);
    });
  }

  res.status(200).json({ llmResponse, toolCallResult, geminiRaw });
}
