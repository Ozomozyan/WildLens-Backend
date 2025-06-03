import api from './api.js';

export const loginRequest = (username, password) =>
  api.post('/login', { username, password }).then((res) => res.data);

/* ===== src/services/DataService.js ===== */
import api from './api.js';

export const getDashboardStats = () => api.get('/stats').then((r) => r.data);
export const getUserList = () => api.get('/users').then((r) => r.data);