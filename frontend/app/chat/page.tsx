"use client";

import { useState } from "react";
import Link from "next/link";
import { CopilotChat } from "@copilotkit/react-ui";
import {
  useCopilotReadable,
  useCopilotChat,
  useCoAgent,
} from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";
import { StateSelector } from "../components/StateSelector";
import { FileUpload } from "../components/FileUpload";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  AlertTriangle,
  ArrowRight,
  FileCheck,
  X,
  Menu,
  ArrowLeft,
  Upload,
  MessageSquare,
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
  // The agent generates these suggestions after each response
  const { state: agentState } = useCoAgent<{
    quick_replies?: string[];
    suggest_brief?: boolean;
    suggest_lawyer?: boolean;
  }>({
    name: "auslaw_agent",
  });

  // Extract quick replies from agent state
  const quickReplies = agentState?.quick_replies;

  // Dynamic initial message based on selected state
  const getInitialMessage = () => {
    if (userState) {
      return `G'day! I'm AusLaw AI, your Australian legal assistant. I see you're in ${userState}. I can help you with:\n\n• Understanding your legal rights\n• Step-by-step guides for legal procedures\n• Finding a lawyer\n\nWhat would you like to know?`;
    }
    return "G'day! I'm AusLaw AI, your Australian legal assistant. Please select your state above so I can provide accurate information for your jurisdiction.";
  };

  // Sidebar content component - reused for desktop and mobile
  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Info Cards */}
      <div className="space-y-4 flex-1 overflow-y-auto">
        {/* State Selector Card */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <MapPin className="h-4 w-4 text-sky-700" />
              Your Location
            </CardTitle>
            <CardDescription>
              Select your state for jurisdiction-specific information.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <StateSelector
              selectedState={userState}
              onStateChange={setUserState}
            />
            {userState && (
              <p className="mt-3 text-sm text-sky-700 bg-sky-50 rounded-lg px-3 py-2">
                Legal information tailored to {userState} law.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Document Upload */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Upload className="h-4 w-4 text-sky-700" />
              Upload Document
            </CardTitle>
            <CardDescription>
              Upload a lease, contract, or legal document for analysis.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FileUpload onFileUploaded={handleFileUploaded} />
            {uploadedDocument && (
              <div className="mt-3 flex items-center gap-2">
                <Badge
                  variant="secondary"
                  className="gap-2 py-1.5 bg-green-50 text-green-800 border-green-200"
                >
                  <FileCheck className="h-3 w-3 text-green-600" />
                  <span className="truncate max-w-[140px]">
                    {uploadedDocument.filename}
                  </span>
                  <button
                    onClick={clearDocument}
                    className="ml-1 hover:text-red-600 transition-colors cursor-pointer"
                    aria-label="Remove document"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-sky-700" />
              Quick Questions
            </CardTitle>
            <CardDescription>
              Click to ask a common question.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            <QuickAction
              text="What are my rights as a tenant?"
              onClose={() => setSidebarOpen(false)}
            />
            <QuickAction
              text="How do I get my bond back?"
              onClose={() => setSidebarOpen(false)}
            />
            <QuickAction
              text="Can my landlord increase rent?"
              onClose={() => setSidebarOpen(false)}
            />
            <QuickAction
              text="I need a lawyer"
              onClose={() => setSidebarOpen(false)}
            />
          </CardContent>
        </Card>
      </div>

      {/* Disclaimer - fixed at bottom */}
      <Alert className="mt-4 border-amber-200 bg-amber-50/80 shrink-0">
        <AlertTriangle className="h-4 w-4 text-amber-600" />
        <AlertTitle className="text-amber-800 text-sm">Disclaimer</AlertTitle>
        <AlertDescription className="text-amber-700 text-xs">
          This tool provides general legal information, not legal advice.
          Consult a qualified lawyer for specific advice.
        </AlertDescription>
      </Alert>
    </div>
  );

  return (
    <div className="flex h-dvh bg-slate-50">
      {/* Mobile Header */}
      <div className="fixed top-0 left-0 right-0 z-40 bg-white/80 backdrop-blur-md border-b border-slate-200 lg:hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="cursor-pointer"
                  aria-label="Open menu"
                >
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80 p-4">
                <SheetHeader className="mb-4">
                  <SheetTitle className="flex items-center gap-2">
                    <Scale className="h-5 w-5 text-sky-700" />
                    AusLaw AI
                  </SheetTitle>
                </SheetHeader>
                <SidebarContent />
              </SheetContent>
            </Sheet>
            <div className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-sky-700" />
              <span className="font-semibold text-slate-900">AusLaw AI</span>
            </div>
          </div>
          <Link href="/">
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-600 cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Home
            </Button>
          </Link>
        </div>
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-80 xl:w-96 flex-col border-r border-slate-200 bg-white">
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <Link href="/" className="flex items-center gap-2 group">
            <Scale className="h-6 w-6 text-sky-700" />
            <span className="text-xl font-semibold text-slate-900 tracking-tight">
              AusLaw AI
            </span>
          </Link>
          <Link href="/">
            <Button
              variant="ghost"
              size="sm"
              className="text-slate-500 hover:text-slate-900 cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Home
            </Button>
          </Link>
        </div>

        {/* Sidebar Body */}
        <div className="flex-1 p-4 overflow-hidden">
          <SidebarContent />
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Add top padding on mobile for fixed header */}
        <div className="flex-1 pt-14 lg:pt-0 flex flex-col">
          <CopilotChat
            className="flex-1"
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
    <Button
      variant="ghost"
      className="w-full justify-start text-left h-auto py-3 px-3 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 cursor-pointer"
      onClick={handleClick}
    >
      <ArrowRight className="mr-2 h-3 w-3 text-slate-400 shrink-0" />
      <span className="truncate">{text}</span>
    </Button>
  );
}

/**
 * QuickRepliesPanel - Renders suggested quick reply buttons from agent state.
 * These are generated by the agent after each response to guide the conversation.
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
    <div className="flex flex-wrap gap-2 p-3 border-t border-slate-100 bg-slate-50/50">
      {replies.map((reply, index) => (
        <Button
          key={index}
          variant="outline"
          size="sm"
          className="text-sm text-slate-700 hover:text-slate-900 hover:bg-white border-slate-200 cursor-pointer"
          onClick={() => handleQuickReply(reply)}
        >
          {reply}
        </Button>
      ))}
    </div>
  );
}
