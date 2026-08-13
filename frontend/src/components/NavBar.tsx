import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/transactions", label: "Transactions" },
  { to: "/tds-events", label: "TDS Events" },
  { to: "/advance-tax", label: "Advance Tax" },
  { to: "/reports", label: "Reports" },
  { to: "/settings", label: "Settings" },
];

export function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <header className="nav-bar">
      <div className="nav-bar__brand">KarAI</div>
      <nav className="nav-bar__links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) => "nav-bar__link" + (isActive ? " nav-bar__link--active" : "")}
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div className="nav-bar__user">
        <span>{user?.full_name}</span>
        <button className="button button--ghost" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </header>
  );
}
