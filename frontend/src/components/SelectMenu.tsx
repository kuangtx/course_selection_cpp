import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Search } from 'lucide-react';

export interface SelectMenuOption {
  value: string;
  label: string;
}

export function SelectMenu({
  label,
  value,
  options,
  onChange,
  searchable = false,
  disabled = false,
  className = '',
  placeholder = '搜索…',
}: {
  label: string;
  value: string;
  options: SelectMenuOption[];
  onChange: (value: string) => void;
  searchable?: boolean;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const root = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const selected = options.find((option) => option.value === value);
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return needle
      ? options.filter((option) => option.label.toLocaleLowerCase().includes(needle))
      : options;
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false);
    };
    const closeEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeEscape);
    if (searchable) requestAnimationFrame(() => search.current?.focus());
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeEscape);
    };
  }, [open, searchable]);

  return (
    <div className={`select-menu ${className}`} ref={root}>
      <button
        type="button"
        className="select-menu-trigger"
        role="combobox"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => {
          setOpen((current) => !current);
          setQuery('');
        }}
      >
        <span className="select-menu-value">{selected?.label ?? value}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="select-menu-popover">
          {searchable && (
            <label className="select-menu-search">
              <Search size={15} aria-hidden="true" />
              <input
                ref={search}
                aria-label={`${label}搜索`}
                placeholder={placeholder}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          )}
          <div className="select-menu-options" role="listbox" aria-label={label}>
            {visible.length ? (
              visible.map((option) => (
                <button
                  type="button"
                  role="option"
                  aria-selected={option.value === value}
                  className={`select-menu-option ${option.value === value ? 'selected' : ''}`}
                  key={option.value}
                  onClick={() => {
                    onChange(option.value);
                    setOpen(false);
                    setQuery('');
                  }}
                >
                  <span>{option.label}</span>
                  {option.value === value && <Check size={15} aria-hidden="true" />}
                </button>
              ))
            ) : (
              <p className="select-menu-empty">没有匹配的学生</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
