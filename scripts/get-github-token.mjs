#!/usr/bin/env node
// Fetch a fresh GitHub access token from the Replit GitHub connector.
// Prints the bare token to stdout so shell scripts can capture it.
import { ReplitConnectors } from '@replit/connectors-sdk';

try {
  const connectors = new ReplitConnectors();
  const conns = await connectors.listConnections({ connectorNames: ['github'] });
  const conn = conns.find((c) => c.status === 'healthy') || conns[0];
  const token = conn?.settings?.access_token || conn?.settings?.oauth?.credentials?.access_token;
  if (!token) {
    console.error('No GitHub access token found in connection settings');
    process.exit(2);
  }
  process.stdout.write(token);
} catch (err) {
  console.error('Failed to fetch GitHub token:', err?.message || err);
  process.exit(1);
}
