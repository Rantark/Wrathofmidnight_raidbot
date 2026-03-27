import { Menu, Sword } from 'lucide-react';
import { useLocation } from 'react-router-dom';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/events': 'Raid Events',
  '/roster': 'Guild Roster',
  '/attendance': 'Attendance',
  '/admin': 'Admin Tools',
  '/characters': 'My Characters',
  '/settings': 'Settings',
};

interface Props {
  onMenuOpen: () => void;
}

export function TopBar({ onMenuOpen }: Props) {
  const { pathname } = useLocation();
  const title = PAGE_TITLES[pathname] ?? 'Wrath of Midnight';

  return (
    <header className="lg:hidden fixed top-0 left-0 right-0 z-30 glass-dark border-b border-gray-700/50 px-4 h-14 flex items-center gap-3">
      <button
        onClick={onMenuOpen}
        className="w-9 h-9 flex items-center justify-center rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
      >
        <Menu size={20} />
      </button>
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg gradient-blue flex items-center justify-center">
          <Sword size={13} className="text-white" />
        </div>
        <span className="font-bold text-sm">{title}</span>
      </div>
    </header>
  );
}
