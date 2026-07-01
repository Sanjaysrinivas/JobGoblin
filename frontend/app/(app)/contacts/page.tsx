import type { Metadata } from "next";

import { ContactListView } from "@/components/contacts/contact-list-view";

export const metadata: Metadata = { title: "Contacts" };

export default function ContactsPage() {
  return <ContactListView />;
}
