import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';
import dotenv from 'dotenv';
dotenv.config();

// Gemini API endpoint and key (expects GEMINI_API_KEY in env)
const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent';
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

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
  try {
    // Gemini expects a POST with { contents: [{ parts: [{ text: prompt }] }] }
    const geminiRes = await axios.post(
      `${GEMINI_API_URL}?key=${GEMINI_API_KEY}`,
      {
        contents: [
          {
            parts: [
              { text: prompt }
            ]
          }
        ]
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    geminiRaw = geminiRes.data;
    console.log('Gemini response:', JSON.stringify(geminiRes, null, 2));
    // Try to extract the text from all possible locations
    if (geminiRaw?.candidates?.length > 0) {
      const parts = geminiRaw.candidates[0]?.content?.parts;
      if (Array.isArray(parts) && parts.length > 0 && parts[0]?.text) {
        llmResponse = parts[0].text;
      } else if (geminiRaw.candidates[0]?.content?.text) {
        llmResponse = geminiRaw.candidates[0].content.text;
      } else {
        llmResponse = JSON.stringify(geminiRaw.candidates[0]);
      }
    } else {
      llmResponse = '[No candidates in Gemini response]';
    }
  } catch (err: any) {
    console.error('Gemini API error:', err?.response?.data || err.message);
    return res.status(500).json({ error: 'Gemini API error', details: err?.response?.data || err.message });
  }

  // Simulate MCP cherry-pick task configuration (replace with actual MCP call)
  // Example: await axios.post('http://localhost:PORT/mcp/cherry-pick', { prompt });
  const mcpResult = `MCP cherry-pick task would be triggered for: ${prompt}`;

  res.status(200).json({ llmResponse, mcpResult, geminiRaw });
}
