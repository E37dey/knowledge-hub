// Top navigation. The links and user identity only appear when logged in;
// on the public auth pages the bar is just the brand.

import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/AuthContext.jsx';

export default function NavBar() {
  const { user, token, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <header className="navbar">
      <Link to="/" className="brand">
        Knowledge&nbsp;Hub
      </Link>
      {token && (
        <nav className="nav-links">
          <Link to="/">Documents</Link>
          <Link to="/ask">Ask</Link>
          {user?.email && <span className="nav-email">{user.email}</span>}
          <button className="btn btn-ghost btn-sm" onClick={handleLogout}>
            Log out
          </button>
        </nav>
      )}
    </header>
  );
}
