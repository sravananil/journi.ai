import { useId, useMemo, useState } from "react";
import type { Location } from "../types";

type Props = {
  label: string;
  icon: string;
  value: Location | null;
  options: Location[];
  placeholder: string;
  onChange: (value: Location | null) => void;
};

export function LocationPicker({ label, icon, value, options, placeholder, onChange }: Props) {
  const inputId = useId();
  const [query, setQuery] = useState(value?.city ?? "");
  const [open, setOpen] = useState(false);
  const matches = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return [];
    return options.filter((place) => place.city.toLocaleLowerCase().includes(needle)).slice(0, 8);
  }, [options, query]);

  function choose(place: Location) {
    onChange(place);
    setQuery(place.city);
    setOpen(false);
  }

  return (
    <div className="field location-field">
      <label htmlFor={inputId}>{label}</label>
      <div className="location-control">
        <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
        <input
          id={inputId}
          autoComplete="off"
          value={query}
          placeholder={placeholder}
          aria-label={label}
          aria-expanded={open && matches.length > 0}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onChange={(event) => {
            setQuery(event.target.value);
            onChange(null);
            setOpen(true);
          }}
        />
        {value && <span className="selected-check material-symbols-outlined" aria-label="Selected">check_circle</span>}
        {open && matches.length > 0 && (
          <div className="location-options" role="listbox">
            {matches.map((place) => (
              <button
                type="button"
                role="option"
                aria-selected={value?.city === place.city}
                key={`${place.city}-${place.lat}-${place.lng}`}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(place)}
              >
                <span className="material-symbols-outlined">location_on</span>
                <span>{place.city}</span>
                <small>{place.country}</small>
              </button>
            ))}
          </div>
        )}
      </div>
      <small className="field-hint">{value ? `${value.city}, ${value.country}` : "Choose a location from the verified JOURNI city list."}</small>
    </div>
  );
}
