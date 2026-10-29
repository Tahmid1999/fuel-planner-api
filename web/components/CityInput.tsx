"use client";

import { AutoComplete } from "antd";
import { useEffect, useRef, useState } from "react";

import { ApiError, type City, type CityChoice, searchCities } from "@/lib/api";
import { WAKING } from "@/lib/copy";
import { useSlow } from "@/lib/useSlow";

// value and onChange come from the antd Form.Item wrapping it.
type Props = {
  value?: CityChoice | null;
  onChange?: (c: CityChoice | null) => void;
  placeholder: string;
  id?: string;
};

export default function CityInput({ value, onChange, placeholder, id }: Props) {
  const [text, setText] = useState(value?.label ?? "");
  const [options, setOptions] = useState<City[]>([]);
  const [noMatch, setNoMatch] = useState(false);
  const [searching, setSearching] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  // City search is a new driver's first request, so it's the one that meets
  // a sleeping server.
  const slow = useSlow(searching);
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
    if (value) onChange?.(null);
    clearTimeout(timer.current);
    latest.current?.abort();
    setNoMatch(false);
    setFailure(null);
    setSearching(false);
    if (q.trim().length < 2) {
      setOptions([]);
      return;
    }
    timer.current = setTimeout(async () => {
      const mine = new AbortController();
      latest.current = mine;
      setSearching(true);
      try {
        const found = await searchCities(q.trim(), mine.signal);
        // a newer search started while this one was in flight
        if (latest.current !== mine) return;
        setOptions(found);
        setNoMatch(found.length === 0);
      } catch (e) {
        if (latest.current !== mine) return;
        setOptions([]);
        if (e instanceof ApiError) setFailure(e.detail);
      } finally {
        if (latest.current === mine) setSearching(false);
      }
    }, 250);
  }

  function onSelect(picked: string) {
    const city = options.find((c) => String(c.id) === picked);
    if (!city) return;
    setText(city.label);
    onChange?.({ id: city.id, label: city.label });
  }

  return (
    <AutoComplete
      id={id}
      value={text}
      options={options.map((c) => ({ value: String(c.id), label: c.label }))}
      onSearch={onSearch}
      onSelect={onSelect}
      notFoundContent={
        failure ?? (slow ? WAKING : noMatch ? "no US city starts with that" : null)
      }
      placeholder={placeholder}
      style={{ width: "100%" }}
    />
  );
}
