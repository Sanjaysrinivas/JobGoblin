import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Settings"
        description="Manage your account, AI provider, and workspace preferences."
      />

      <div className="grid max-w-3xl gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>Your sign-in details.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                defaultValue="you@example.com"
                disabled
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="name">Display name</Label>
              <Input id="name" placeholder="Your name" disabled />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI provider</CardTitle>
            <CardDescription>
              JobGoblin runs analysis and generation through a pluggable
              provider.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div className="space-y-0.5">
                <p className="text-sm font-medium">Ollama (local)</p>
                <p className="text-muted-foreground text-xs">
                  qwen2.5:7b-instruct · runs on your hardware
                </p>
              </div>
              <Badge variant="success">Active</Badge>
            </div>
            <p className="text-muted-foreground text-xs">
              Provider configuration is read from the server environment
              (AI_PROVIDER). Editing from the UI lands in a later release.
            </p>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button disabled>Save changes</Button>
        </div>
      </div>
    </div>
  );
}
