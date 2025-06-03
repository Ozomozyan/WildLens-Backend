// src/context/AuthContext.jsx
import { createContext, useContext, useState } from "react";
import axios from "axios";
import api   from "../services/api";

export const AuthContext = createContext();

/* handy hook */
export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {

  /* ---- initial load: pull everything from localStorage ---- */
  const [user, setUser] = useState(() => {
    const token  = localStorage.getItem("token");
    const role   = localStorage.getItem("role");
    const userId = localStorage.getItem("user_id");

    if (token && role && userId) {
      // put the token on every axios / api request
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
      api.defaults.headers.common["Authorization"]   = `Bearer ${token}`;
      return { id: userId, role, token };      //  ← keep token here
    }
    return null;                               // not logged-in
  });

  /* ---- helper that any component may call ---- */
  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("user_id");
    delete axios.defaults.headers.common["Authorization"];
    delete api.defaults.headers.common["Authorization"];
    setUser(null);
  }

  /* ---- give everything to children ---- */
  return (
    <AuthContext.Provider value={{ user, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
