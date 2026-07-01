/**
 * Contact API helpers. Thin wrappers over the `/api/contacts` CRUD contract.
 */

import { api } from "@/lib/api";
import type {
  Contact,
  ContactCreatePayload,
  ContactUpdatePayload,
} from "@/lib/types";

export interface ContactJobOption {
  id: string;
  company_name: string;
  title: string;
  location: string | null;
}

/** GET /api/contacts - list the current user's saved contacts. */
export function listContacts(): Promise<Contact[]> {
  return api.get<Contact[]>("/contacts");
}

/** GET /api/jobs - list saved jobs for contact linking. */
export function listContactJobs(): Promise<ContactJobOption[]> {
  return api.get<ContactJobOption[]>("/jobs");
}

/** GET /api/contacts/{id} - fetch one saved contact. */
export function getContact(id: string): Promise<Contact> {
  return api.get<Contact>(`/contacts/${id}`);
}

/** POST /api/contacts - create a recruiter, referral, or hiring contact. */
export function createContact(payload: ContactCreatePayload): Promise<Contact> {
  return api.post<Contact>("/contacts", payload);
}

/** PATCH /api/contacts/{id} - update editable contact fields. */
export function updateContact(
  id: string,
  payload: ContactUpdatePayload
): Promise<Contact> {
  return api.patch<Contact>(`/contacts/${id}`, payload);
}

/** DELETE /api/contacts/{id} - remove a saved contact. */
export function deleteContact(id: string): Promise<void> {
  return api.delete<void>(`/contacts/${id}`);
}
