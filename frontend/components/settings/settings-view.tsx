"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import {
  getRuntimeConfiguration,
  type RuntimeConfiguration,
} from "@/lib/runtime";
import type { User } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function title(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function SettingsView() {
  const [user, setUser] = React.useState<User | null>(null);
  const [runtime, setRuntime] = React.useState<RuntimeConfiguration | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    Promise.all([getCurrentUser(), getRuntimeConfiguration()])
      .then(([account, configuration]) => {
        if (!active) return;
        setUser(account);
        setRuntime(configuration);
      })
      .catch(() => {
        if (active) setError("Could not load the current server configuration.");
      });
    return () => {
      active = false;
    };
  }, []);

  if (!user || !runtime) {
    return (
      <div className="space-y-3">
        {error ? (
          <p className="text-destructive text-sm">{error}</p>
        ) : (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading settings...
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="grid max-w-3xl gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Your current authenticated account.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={user.email} readOnly />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Display name</Label>
            <Input id="name" value={user.display_name} readOnly />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Runtime providers</CardTitle>
          <CardDescription>
            Read-only values from the backend environment. Availability is checked
            when an operation runs.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">AI provider</p>
              <p className="text-muted-foreground text-xs">
                {title(runtime.ai_provider)} · Model: {runtime.ai_model}
                {runtime.local_ai ? " · configured for local execution" : ""}
              </p>
            </div>
            <Badge variant="outline">Configured</Badge>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Job discovery</p>
              <p className="text-muted-foreground text-xs">
                Provider: {runtime.discovery_provider}
              </p>
            </div>
            <Badge variant="outline">Configured</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
