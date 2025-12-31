import express from 'express';
import cors from 'cors';
import { WebSocketServer } from 'ws';

const PORT = process.env.PORT || 4001;

const app = express();
app.disable('x-powered-by');
app.use(cors({ origin: '*', methods: ['GET','POST'] }));
app.use(express.json());

app.get('/health', (_req, res) => {
  res.json({ ok: true, ts: Date.now(), service: 'coti-microservice' });
});

const server = app.listen(PORT, () => {
  console.log(`Microservice listening on http://localhost:${PORT}`);
});

// WebSocket echo/broadcast minimal
const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'welcome', ts: Date.now() }));
  ws.on('message', (msg) => {
    // broadcast to all clients
    wss.clients.forEach(client => {
      if (client.readyState === 1) {
        client.send(JSON.stringify({ type: 'broadcast', payload: msg.toString(), ts: Date.now() }));
      }
    });
  });
});
