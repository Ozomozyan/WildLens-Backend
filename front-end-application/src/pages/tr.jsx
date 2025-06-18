/* ─── src/pages/LoginPage.jsx ──────────────────────────────────────── */
import { useState, useContext } from "react";
import { useNavigate }           from "react-router-dom";
import axios                     from "axios";
import { AuthContext }           from "../context/AuthContext.jsx";
import api                       from "../services/api";
import logo                      from "../assets/logo.png";              // ← add

export default function LoginPage() {
  const { setUser } = useContext(AuthContext);
  const navigate    = useNavigate();

  /* form state */
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");

  /* ── submit ─────────────────────────────────────────────────────── */
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    try {
      const { data } = await axios.post(
        `${import.meta.env.VITE_API_URL}/login/`,
        { email, password }
      );                                       // { token, user_id, role }

      /* persist & set headers */
      localStorage.setItem("token",   data.token);
      localStorage.setItem("role",    data.role);
      localStorage.setItem("user_id", data.user_id);
      axios.defaults.headers.common["Authorization"] = `Bearer ${data.token}`;
      api.defaults.headers.common["Authorization"]   = `Bearer ${data.token}`;

      /* context + redirect */
      setUser({ id: data.user_id, role: data.role });
      navigate(data.role === "admin" ? "/admin" : "/dashboard");

    } catch {
      setError("Invalid credentials");
    }
  }

  /* ── UI ─────────────────────────────────────────────────────────── */
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gradient-to-br from-emerald-50 to-teal-100">
      {/* decorative blob */}
      <div className="absolute -top-10 -left-10 h-72 w-72 rounded-full bg-[#32C48E]/20 blur-3xl" />
      <div className="absolute -bottom-16 -right-16 h-96 w-72 rotate-12 rounded-3xl bg-[#32C48E]/30 blur-2xl" />

      {/* card */}
      <form
        onSubmit={handleSubmit}
        className="z-10 w-full max-w-sm space-y-5 rounded-2xl bg-white/90 p-8 shadow-lg backdrop-blur-md sm:p-10"
      >
        {/* logo */}
        <div className="flex items-center justify-center">
          <img src={logo} alt="WildLens Logo" className="h-14 w-auto" />
        </div>

        <h1 className="text-center text-2xl font-bold text-[#32C48E]">
          Sign in to WildLens
        </h1>

        {error && (
          <p className="rounded bg-red-50 py-2 text-center text-sm font-medium text-red-600">
            {error}
          </p>
        )}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="input-field"
          required
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input-field"
          required
        />

        <button
          type="submit"
          className="btn-primary w-full py-2"
          style={{ backgroundColor: "#32C48E" }}
        >
          Sign In
        </button>
      </form>
    </div>
  );
}

/* ─── tailwind helpers (global CSS / index.css) ──────────────────────
You only need to add these once; other pages can reuse them.

  @layer components {
    .input-field {
      @apply w-full rounded-lg border border-gray-300 bg-white/70 px-3 py-2 text-sm
              placeholder-gray-400 shadow-sm focus:border-[#32C48E] focus:ring-2
              focus:ring-[#32C48E]/30;
    }
    .btn-primary {
      @apply rounded-lg text-center font-semibold text-white transition
              hover:brightness-110 active:scale-[.98];
    }
  }
*/
