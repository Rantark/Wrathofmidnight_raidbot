import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Calendar, Users, BarChart2, UserCog, LogOut, X, Sword, Tag,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/events',    icon: Calendar,         label: 'Raid Events' },
  { to: '/roster',    icon: Users,            label: 'Guild Roster' },
  { to: '/attendance',icon: BarChart2,        label: 'Attendance' },
  { to: '/changelog', icon: Tag,              label: 'Changelog' },
];

export function MobileMenu({ isOpen, onClose }: Props) {
  const { user, isRaidLeader, isOfficer, logout } = useAuth();

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden transition-opacity duration-300 ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      />

      {/* Drawer */}
      <div
        className={`fixed top-0 left-0 h-full w-72 glass-dark z-50 lg:hidden transition-transform duration-300 ease-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-4 py-5 border-b border-gray-700/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl gradient-blue flex items-center justify-center">
              <Sword size={16} className="text-white" />
            </div>
            <div>
              <p className="font-bold text-sm">Wrath of Midnight</p>
              <p className="text-gray-400 text-xs">Raid Portal</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-white hover:bg-white/10"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
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
              <NavLink
                to="/admin"
                onClick={onClose}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <UserCog size={18} />
                <span>Admin Tools</span>
              </NavLink>
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="absolute bottom-0 left-0 right-0 px-3 pb-6 border-t border-gray-700/50 pt-3">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="w-9 h-9 rounded-full" />
            ) : (
              <div className="w-9 h-9 rounded-full gradient-blue flex items-center justify-center text-sm font-bold">
                {user?.username?.[0]?.toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{user?.username}</p>
              <p className="text-xs text-gray-400 capitalize">{user?.role?.replace('_', ' ')}</p>
            </div>
          </div>
          <button
            onClick={() => { logout(); onClose(); }}
            className="nav-item w-full text-red-400 hover:text-red-300 hover:bg-red-500/10"
          >
            <LogOut size={18} />
            <span>Sign out</span>
          </button>
        </div>
      </div>
    </>
  );
}
