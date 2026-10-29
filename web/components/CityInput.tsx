"use client";

import { AutoComplete } from "antd";
import { useEffect, useRef, useState } from "react";

import { type City, type CityChoice, searchCities } from "@/lib/api";

type Props = {
  value: CityChoice | null;
  onChange: (c: CityChoice | null) => void;
  placeholder: string;
  status?: "error";
  id?: string;
};

export default function CityInput({ value, onChange, placeholder, status, id }: Props) {
  const [text, setText] = useState(value?.label ?? "");
  const [options, setOptions] = useState<City[]>([]);
  const [noMatch, setNoMatch] = useState(false);
  const latest = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  // A city set from outside (a saved plan) shows its label.
  useEffect(() => {
    if (value) setText(value.label);
  }, [value]);

  useEffect(
    () => () => {
      clearTimeout(timer.current);
      latest.current?.abort();
    },
    [],
  );

  function onSearch(q: string) {
    setText(q);
    if (value) onChange(null);
    clearTimeout(timer.current);
    latest.current?.abort();
    setNoMatch(false);
    if (q.trim().length < 2) {
      setOptions([]);
      return;
    }
    timer.current = setTimeout(async () => {
      const mine = new AbortController();
      latest.current = mine;
      try {
        const found = await searchCities(q.trim(), mine.signal);
        // a newer search started while this one was in flight
        if (latest.current !== mine) return;
        setOptions(found);
        setNoMatch(found.length === 0);
      } catch {
        if (latest.current === mine) setOptions([]);
      }
    }, 250);
  }

  function onSelect(picked: string) {
    const city = options.find((c) => String(c.id) === picked);
    if (!city) return;
    setText(city.label);
    onChange({ id: city.id, label: city.label });
  }

  return (
    <AutoComplete
      id={id}
      value={text}
      options={options.map((c) => ({ value: String(c.id), label: c.label }))}
      onSearch={onSearch}
      onSelect={onSelect}
      notFoundContent={noMatch ? "no US city starts with that" : null}
      placeholder={placeholder}
      status={status}
      style={{ width: "100%" }}
    />
  );
}
