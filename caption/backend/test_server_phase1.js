const http = require('http');

console.log('🧪 Testing Backend Server Health & Endpoints...\n');

// Start backend server on test port 5001 or check running server
const express = require('express');
const app = require('./server.js'); // server.js starts listening automatically

setTimeout(() => {
  http.get('http://localhost:5000/api/health', (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      console.log('Health Endpoint Response:', data);
      console.log('✅ Backend API Health Test PASSED.');
      process.exit(0);
    });
  }).on('error', (err) => {
    console.error('❌ Health check failed:', err.message);
    process.exit(1);
  });
}, 1000);
