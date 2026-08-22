"use client";

import { useState } from "react";

interface PasswordInputProps {
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  minLength?: number;
  required?: boolean;
}

export function PasswordInput({ value, onChange, autoComplete, minLength, required }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        name="password"
        autoComplete={autoComplete}
        minLength={minLength}
        className="w-full rounded-md border border-gray-300 px-3 py-2 pr-16"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 px-3 text-xs text-gray-500"
        tabIndex={-1}
      >
        {visible ? "숨기기" : "보기"}
      </button>
    </div>
  );
}
