"use client";

import { useState } from "react";
import Link from "next/link";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import {
  useCopilotReadable,
  useCopilotChat,
  useCoAgent,
} from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";
import { StateSelector } from "../components/StateSelector";
import { FileUpload } from "../components/FileUpload";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Scale,
  MapPin,
  FileCheck,
  X,
  Menu,
  ArrowLeft,
  Upload,
  FileText,
  Sparkles,
  ChevronRight,
  Shield,
} from "lucide-react";

export default function ChatPage() {
  const [userState, setUserState] = useState<string | null>(null);
  const [uploadedDocument, setUploadedDocument] = useState<{
    url: string;
    filename: string;
  } | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Share user's state/territory with the Copilot agent
  useCopilotReadable({
    description: "The user's Australian state/territory for legal queries",
    value: userState
      ? `User is in ${userState}. Use state="${userState}" for lookup_law, find_lawyer, and generate_checklist tools.`
      : "User has not selected their state yet.",
  });

  // Share uploaded document URL with the Copilot agent
  useCopilotReadable({
    description: "Uploaded document URL for analysis",
    value: uploadedDocument
      ? `The user has uploaded a document named "${uploadedDocument.filename}". The document URL is: ${uploadedDocument.url}\n\nWhen the user asks to analyze this document, use the analyze_document tool with document_url="${uploadedDocument.url}". Automatically detect the document type (lease, contract, visa, or general) based on the filename or user's request.`
      : "No document uploaded yet.",
  });

  const handleFileUploaded = (url: string, filename: string) => {
    setUploadedDocument({ url, filename });
  };

  const clearDocument = () => {
    setUploadedDocument(null);
  };

  // Access agent state for quick replies
  const { state: agentState } = useCoAgent<{
    quick_replies?: string[];
    suggest_brief?: boolean;
    suggest_lawyer?: boolean;
  }>({
    name: "auslaw_agent",
  });

  const quickReplies = agentState?.quick_replies;

  // Dynamic initial message based on selected state
  const getInitialMessage = () => {
    if (userState) {
      return `G'day! I'm your AusLaw AI assistant. I see you're in **${userState}**.\n\nI can help you with:\n• Understanding your legal rights\n• Step-by-step guides for legal procedures\n• Finding a qualified lawyer\n\nHow can I assist you today?`;
    }
    return "G'day! I'm your AusLaw AI assistant. Please select your state/territory from the sidebar so I can provide jurisdiction-specific guidance.";
  };

  // Sidebar content component
  const SidebarContent = () => (
    <div className="flex flex-col h-full gap-6">
      {/* Location Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <MapPin className="h-4 w-4 text-primary" />
          Your Jurisdiction
        </div>
        <StateSelector
          selectedState={userState}
          onStateChange={setUserState}
        />
        {userState && (
          <div className="flex items-center gap-2 text-xs text-primary bg-primary/5 rounded-lg px-3 py-2 border border-primary/10">
            <Shield className="h-3.5 w-3.5" />
            <span>Legal info tailored to {userState}</span>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="h-px bg-slate-200" />

      {/* Document Upload Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <Upload className="h-4 w-4 text-primary" />
          Document Analysis
        </div>
        <FileUpload onFileUploaded={handleFileUploaded} />
        {uploadedDocument && (
          <Badge
            variant="secondary"
            className="gap-2 py-2 px-3 bg-emerald-50 text-emerald-700 border border-emerald-200 w-full justify-start"
          >
            <FileCheck className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
            <span className="truncate flex-1 text-left">
              {uploadedDocument.filename}
            </span>
            <button
              onClick={clearDocument}
              className="hover:text-red-600 transition-colors cursor-pointer ml-auto"
              aria-label="Remove document"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </Badge>
        )}
        <p className="text-xs text-slate-500">
          Upload leases, contracts, or legal documents for AI analysis.
        </p>
      </div>

      {/* Divider */}
      <div className="h-px bg-slate-200" />

      {/* Quick Actions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <Sparkles className="h-4 w-4 text-primary" />
          Quick Questions
        </div>
        <div className="space-y-1.5">
          <QuickAction
            text="What are my tenant rights?"
            onClose={() => setSidebarOpen(false)}
          />
          <QuickAction
            text="How do I get my bond back?"
            onClose={() => setSidebarOpen(false)}
          />
          <QuickAction
            text="Help me find a lawyer"
            onClose={() => setSidebarOpen(false)}
          />
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Generate Brief Button */}
      <GenerateBriefButton onClose={() => setSidebarOpen(false)} />

      {/* Disclaimer */}
      <div className="p-3 bg-amber-50/80 border border-amber-200/60 rounded-lg">
        <p className="text-xs text-amber-800 leading-relaxed">
          <span className="font-medium">Disclaimer:</span> This tool provides
          general legal information only, not legal advice. Always consult a
          qualified solicitor for specific matters.
        </p>
      </div>
    </div>
  );

  return (
    <div className="flex h-dvh bg-slate-50">
      {/* Mobile Header */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-white/90 backdrop-blur-md border-b border-slate-200/80 lg:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="cursor-pointer hover:bg-slate-100"
                  aria-label="Open menu"
                >
                  <Menu className="h-5 w-5 text-slate-600" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 p-5">
                <SheetHeader className="mb-6">
                  <SheetTitle className="flex items-center gap-2.5 text-lg">
                    <div className="p-1.5 bg-primary/10 rounded-lg">
                      <Scale className="h-5 w-5 text-primary" />
                    </div>
                    <span className="font-semibold">AusLaw AI</span>
                  </SheetTitle>
                </SheetHeader>
                <SidebarContent />
              </SheetContent>
            </Sheet>

            <div className="flex items-center gap-2">
              <div className="p-1 bg-primary/10 rounded-md">
                <Scale className="h-5 w-5 text-primary" />
              </div>
              <span className="font-semibold text-slate-900">AusLaw AI</span>
            </div>
          </div>

          <Link href="/">
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-500 hover:text-slate-900 cursor-pointer gap-1"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Home</span>
            </Button>
          </Link>
        </div>
      </header>

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-80 xl:w-[340px] flex-col border-r border-slate-200/80 bg-white">
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="p-1.5 bg-primary/10 rounded-lg group-hover:bg-primary/15 transition-colors">
              <Scale className="h-6 w-6 text-primary" />
            </div>
            <span className="text-xl font-semibold text-slate-900 tracking-tight">
              AusLaw AI
            </span>
          </Link>
          <Link href="/">
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-400 hover:text-slate-700 cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
        </div>

        {/* Sidebar Body */}
        <div className="flex-1 p-5 overflow-y-auto">
          <SidebarContent />
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-gradient-to-b from-slate-50 to-white">
        {/* Add top padding on mobile for fixed header */}
        <div className="flex-1 pt-14 lg:pt-0 flex flex-col min-h-0 overflow-hidden">
          <CopilotChat
            className="flex-1 min-h-0"
            labels={{
              title: "AusLaw AI",
              initial: getInitialMessage(),
            }}
          />

          {/* Quick Replies from agent state */}
          {quickReplies && quickReplies.length > 0 && (
            <QuickRepliesPanel replies={quickReplies} />
          )}
        </div>
      </main>
    </div>
  );
}

/**
 * QuickAction - Sidebar quick question button
 */
function QuickAction({
  text,
  onClose,
}: {
  text: string;
  onClose?: () => void;
}) {
  const { appendMessage } = useCopilotChat();

  const handleClick = async () => {
    await appendMessage(
      new TextMessage({
        role: MessageRole.User,
        content: text,
      })
    );
    onClose?.();
  };

  return (
    <button
      onClick={handleClick}
      className="w-full flex items-center gap-2 text-left text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg px-3 py-2.5 transition-colors cursor-pointer group"
    >
      <ChevronRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-primary transition-colors" />
      <span>{text}</span>
    </button>
  );
}

/**
 * QuickRepliesPanel - Renders suggested quick reply buttons from agent state
 */
function QuickRepliesPanel({ replies }: { replies: string[] }) {
  const { appendMessage } = useCopilotChat();

  const handleQuickReply = async (reply: string) => {
    await appendMessage(
      new TextMessage({
        role: MessageRole.User,
        content: reply,
      })
    );
  };

  return (
    <div className="flex flex-wrap gap-2 p-4 border-t border-slate-200/80 bg-white/80 backdrop-blur-sm">
      <span className="text-xs text-slate-400 w-full mb-1">Suggested:</span>
      {replies.map((reply, index) => (
        <Button
          key={index}
          variant="outline"
          size="sm"
          className="text-sm text-slate-600 hover:text-slate-900 hover:bg-white hover:border-primary/30 border-slate-200 cursor-pointer transition-all"
          onClick={() => handleQuickReply(reply)}
        >
          {reply}
        </Button>
      ))}
    </div>
  );
}

/**
 * GenerateBriefButton - Triggers lawyer brief generation
 */
function GenerateBriefButton({ onClose }: { onClose?: () => void }) {
  const { appendMessage, isLoading } = useCopilotChat();

  const handleGenerateBrief = async () => {
    await appendMessage(
      new TextMessage({
        role: MessageRole.User,
        content:
          "[GENERATE_BRIEF] Please prepare a lawyer brief based on our conversation.",
      })
    );
    onClose?.();
  };

  return (
    <Button
      onClick={handleGenerateBrief}
      disabled={isLoading}
      className="w-full bg-primary hover:bg-primary/90 text-white cursor-pointer gap-2 h-11 text-sm font-medium shadow-sm shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
    >
      <FileText className="h-4 w-4" />
      Generate Lawyer Brief
    </Button>
  );
}
