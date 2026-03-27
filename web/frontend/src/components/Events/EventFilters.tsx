interface Props {
  typeFilter: string;
  onTypeChange: (t: string) => void;
}

const EVENT_TYPES = [
  'All Types',
  'Normal Raid', 'Heroic Raid', 'Mythic Raid',
  'Mythic+ Night', 'PvP - RBG', 'PvP - Arena',
  'Achievement Run', 'Alt Raid', 'Social Event',
];

export function EventFilters({ typeFilter, onTypeChange }: Props) {
  return (
    <div className="flex items-center gap-2">
      <select
        value={typeFilter}
        onChange={(e) => onTypeChange(e.target.value)}
        className="input max-w-[180px] text-xs py-2"
      >
        {EVENT_TYPES.map((t) => (
          <option key={t} value={t === 'All Types' ? '' : t}>{t}</option>
        ))}
      </select>
    </div>
  );
}
