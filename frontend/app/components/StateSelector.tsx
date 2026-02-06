"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MapPin } from "lucide-react";

const STATES = [
  { code: "VIC", name: "Victoria" },
  { code: "NSW", name: "New South Wales" },
  { code: "QLD", name: "Queensland" },
  { code: "SA", name: "South Australia" },
  { code: "WA", name: "Western Australia" },
  { code: "TAS", name: "Tasmania" },
  { code: "NT", name: "Northern Territory" },
  { code: "ACT", name: "Australian Capital Territory" },
];

interface StateSelectorProps {
  selectedState: string | null;
  onStateChange: (state: string) => void;
}

export function StateSelector({ selectedState, onStateChange }: StateSelectorProps) {
  return (
    <Select value={selectedState || undefined} onValueChange={onStateChange}>
      <SelectTrigger className="w-full h-10">
        <MapPin className="mr-2 h-4 w-4 text-muted-foreground" />
        <SelectValue placeholder="Select your state" />
      </SelectTrigger>
      <SelectContent>
        {STATES.map((state) => (
          <SelectItem key={state.code} value={state.code}>
            <span className="font-medium">{state.code}</span>
            <span className="text-muted-foreground ml-2">- {state.name}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
