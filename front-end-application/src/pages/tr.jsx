/* ─── src/components/Navbar.jsx ─────────────────────────── */
import { useContext, Fragment } from "react";
import { NavLink }              from "react-router-dom";
import { AuthContext }          from "../context/AuthContext.jsx";

/* Tailwind helpers ------------------------------------------------------ */
const base = "px-2 py-1 rounded hover:bg-gray-700";
const active = "underline decoration-2";

function MenuLink({ to, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `${base} ${isActive ? active : ""}`
      }
    >
      {label}
    </NavLink>
  );
}

export default function Navbar() {
  const { user, logout } = useContext(AuthContext);

  /* links everyone gets ----------------------------------------------- */
  const common = [
    { to: "/dashboard",        label: "Dashboard"        },
    { to: "/predict",          label: "Predict"          },
    { to: "/map",              label: "Map"              },
    { to: "/species-summary",  label: "Species Summary"  },
  ];

  /* extras only for admin --------------------------------------------- */
  const admin = [
    { to: "/admin",     label: "Admin Panel" },
    { to: "/admin/qc",  label: "Data Quality"},
    { to: "/logs",      label: "Logs"        },
  ];

  return (
    <nav className="flex items-center justify-between px-4 py-3 bg-gray-800 text-white">
      <span className="text-lg font-semibold">Wild Dashboard</span>

      {user ? (
        <div className="flex items-center gap-3">
          {/* regular pages */}
          {common.map(link => (
            <MenuLink key={link.to} {...link} />
          ))}

          {/* admin-only pages */}
          {user.role === "admin" &&
            admin.map(link => (
              <MenuLink key={link.to} {...link} />
            ))}

          {/* logout button */}
          <button
            onClick={logout}
            className="ml-2 px-3 py-1 rounded bg-red-500 hover:bg-red-600"
          >
            Logout
          </button>
        </div>
      ) : (
        /* if the user is not logged-in just a “Login” link */
        <NavLink to="/login" className={base}>
          Login
        </NavLink>
      )}
    </nav>
  );
}
