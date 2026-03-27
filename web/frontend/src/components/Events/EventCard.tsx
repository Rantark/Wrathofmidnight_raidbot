import { Calendar, Lock, Users, ExternalLink } from 'lucide-react';
import { RaidEvent } from '@/types';
import { formatEventDate } from '@/lib/utils';
import { EVENT_TYPE_COLORS } from '@/types';
import { Link } from 'react-router-dom';

interface Props {
  event: RaidEvent;
  signupCount?: number;
  confirmedCount?: number;
}

export function EventCard({ event, signupCount, confirmedCount }: Props) {
  const typeColor = EVENT_TYPE_COLORS[event.event_type] ?? '#6366f1';
  const total = event.max_tanks + event.max_healers + event.max_dps;

  return (
    <Link to={`/events/${event.event_id}`} className="block">
      <div className="glass rounded-xl p-4 hover:bg-white/5 transition-all duration-200 group">
        {/* Color bar */}
        <div className="h-1 rounded-full mb-3" style={{ background: typeColor }} />

        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="badge text-white"
                style={{ background: `${typeColor}33`, border: `1px solid ${typeColor}55` }}
              >
                {event.event_type}
              </span>
              {event.locked === 1 && (
                <span className="badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                  <Lock size={10} /> Locked
                </span>
              )}
            </div>
            <h3 className="font-bold text-sm lg:text-base truncate group-hover:text-indigo-300 transition-colors">
              {event.event_name}
            </h3>
          </div>
          <ExternalLink size={14} className="text-gray-600 group-hover:text-gray-400 shrink-0 mt-1 transition-colors" />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-400">
          <span className="flex items-center gap-1.5">
            <Calendar size={12} />
            {formatEventDate(event.event_date, event.event_time)}
          </span>
          {confirmedCount !== undefined && (
            <span className="flex items-center gap-1.5">
              <Users size={12} />
              {confirmedCount}/{total} signed up
            </span>
          )}
        </div>

        {event.description && (
          <p className="mt-2 text-xs text-gray-500 line-clamp-2">{event.description}</p>
        )}
      </div>
    </Link>
  );
}
