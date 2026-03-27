export type UserRole = 'member' | 'raid_leader' | 'officer';

export interface User {
  user_id: string;
  username: string;
  role: UserRole;
  guild_id: string;
  avatar_url?: string;
}

export interface Character {
  discord_id: string;
  guild_id: string;
  char_name: string;
  char_class: string;
  main_spec: string;
  off_spec?: string;
  is_main: number;
  ilvl?: number;
  realm?: string;
  region?: string;
  avatar_url?: string;
  raiderio_url?: string;
  professions?: string;
  progression?: string;
  race?: string;
  faction?: string;
  notes?: string;
}

export interface RaidEvent {
  event_id: number;
  guild_id: string;
  event_name: string;
  event_type: string;
  event_date: string;
  event_time: string;
  description?: string;
  channel_id?: string;
  message_id?: string;
  created_by: string;
  max_tanks: number;
  max_healers: number;
  max_dps: number;
  locked: number;
  status: 'active' | 'cancelled' | 'completed';
  color?: number;
}

export interface Signup {
  signup_id: number;
  event_id: number;
  discord_id: string;
  char_name: string;
  char_class: string;
  main_spec: string;
  role: 'tank' | 'healer' | 'dps';
  signup_status: 'confirmed' | 'bench' | 'tentative' | 'declined';
  signup_time: string;
}

export interface AttendanceStats {
  total: number;
  present: number;
  late: number;
  excused: number;
  absent: number;
  percentage: number;
}

export interface AttendanceRecord {
  attendance_id: number;
  event_id: number;
  discord_id: string;
  char_name: string;
  status: 'present' | 'absent' | 'late' | 'excused';
  timestamp: string;
}

export interface AttendanceHistory {
  event_id: number;
  event_name: string;
  event_date: string;
  event_type: string;
  status: string;
  timestamp: string;
}

export interface Absence {
  absence_id: number;
  discord_id: string;
  guild_id: string;
  event_id?: number;
  event_name?: string;
  event_date?: string;
  reason: string;
  submitted_at: string;
}

export interface Template {
  template_id: number;
  guild_id: string;
  template_name: string;
  event_name: string;
  event_type: string;
  event_time: string;
  description?: string;
  max_tanks: number;
  max_healers: number;
  max_dps: number;
  created_by: string;
}

export interface Permission {
  discord_id: string;
  role: 'raid_leader' | 'officer';
  username?: string;
}

export interface GuildConfig {
  guild_id: number;
  event_channel_id?: number;
  log_channel_id?: number;
  attendance_threshold: number;
  timezone: string;
  default_max_tanks: number;
  default_max_healers: number;
  default_max_dps: number;
  roster_channel_id?: number;
  roster_message_id?: number;
}

export const CLASS_COLORS: Record<string, string> = {
  Warrior: '#C79C6E',
  Paladin: '#F58CBA',
  Hunter: '#ABD473',
  Rogue: '#FFF569',
  Priest: '#E8E8E8',
  'Death Knight': '#C41F3B',
  Shaman: '#0070DE',
  Mage: '#40C7EB',
  Warlock: '#8788EE',
  Monk: '#00FF96',
  Druid: '#FF7D0A',
  'Demon Hunter': '#A330C9',
  Evoker: '#33937F',
};

export const ROLE_ICONS: Record<string, string> = {
  tank: '🛡️',
  healer: '💚',
  dps: '⚔️',
};

export const EVENT_TYPES = [
  'Normal Raid',
  'Heroic Raid',
  'Mythic Raid',
  'Mythic+ Night',
  'PvP - RBG',
  'PvP - Arena',
  'Achievement Run',
  'Alt Raid',
  'Social Event',
] as const;

export const EVENT_TYPE_COLORS: Record<string, string> = {
  'Mythic Raid': '#ef4444',
  'Heroic Raid': '#f97316',
  'Normal Raid': '#22c55e',
  'Mythic+ Night': '#8b5cf6',
  'PvP - RBG': '#ec4899',
  'PvP - Arena': '#f43f5e',
  'Achievement Run': '#eab308',
  'Alt Raid': '#6366f1',
  'Social Event': '#14b8a6',
};
