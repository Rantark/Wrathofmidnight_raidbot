import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Calendar, Users, BarChart2, UserCog, LogOut, Sword, Tag,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/events',    icon: Calendar,         label: 'Raid Events' },
  { to: '/roster',    icon: Users,            label: 'Guild Roster' },
  { to: '/attendance',icon: BarChart2,        label: 'Attendance' },
  { to: '/changelog', icon: Tag,              label: 'Changelog' },
];

const adminItems = [
  { to: '/admin', icon: UserCog, label: 'Admin Tools' },
];

export function Sidebar() {
  const { user, isRaidLeader, isOfficer, logout } = useAuth();

  return (
    <aside className="hidden lg:flex flex-col w-64 glass-dark border-r border-gray-700/50 min-h-screen fixed left-0 top-0 z-30">
      {/* Logo */}
      <div className="px-6 py-6 border-b border-gray-700/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl gradient-blue flex items-center justify-center shrink-0">
            <Sword size={20} className="text-white" />
          </div>
          <div className="min-w-0">
            <p className="font-bold text-sm leading-tight truncate">Wrath of Midnight</p>
            <p className="text-gray-400 text-xs">Raid Portal <span className="font-mono">v1.6.0</span></p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}

        {(isRaidLeader || isOfficer) && (
          <>
            <div className="pt-3 pb-1 px-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Admin</p>
            </div>
            {adminItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* User footer */}
      <div className="px-3 pb-4 border-t border-gray-700/50 pt-3">
        <div className="flex items-center gap-3 px-3 py-2 mb-2 rounded-xl">
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full" />
          ) : (
            <div className="w-8 h-8 rounded-full gradient-blue flex items-center justify-center text-xs font-bold">
              {user?.username?.[0]?.toUpperCase()}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold truncate">{user?.username}</p>
            <p className="text-xs text-gray-400 capitalize">{user?.role?.replace('_', ' ')}</p>
          </div>
        </div>
        <button onClick={logout} className="nav-item w-full text-red-400 hover:text-red-300 hover:bg-red-500/10">
          <LogOut size={18} />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}
