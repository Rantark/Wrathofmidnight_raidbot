import { format, parseISO, formatDistanceToNow } from 'date-fns';
import { CLASS_COLORS } from '@/types';

export function classColor(charClass: string): string {
  return CLASS_COLORS[charClass] ?? '#9ca3af';
}

export function formatEventDate(date: string, time: string): string {
  try {
    return format(parseISO(`${date}T${time}`), 'EEE, MMM d · h:mm a');
  } catch {
    return `${date} ${time}`;
  }
}

export function formatRelativeDate(date: string): string {
  try {
    return formatDistanceToNow(parseISO(date), { addSuffix: true });
  } catch {
    return date;
  }
}

export function attendanceBadge(pct: number): { color: string; label: string } {
  if (pct >= 90) return { color: 'text-green-400', label: 'Excellent' };
  if (pct >= 75) return { color: 'text-yellow-400', label: 'Good' };
  if (pct >= 50) return { color: 'text-orange-400', label: 'Fair' };
  return { color: 'text-red-400', label: 'Low' };
}

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ');
}
