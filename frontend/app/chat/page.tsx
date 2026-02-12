"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";
import {
  useCopilotReadable,
  useCopilotChat,
  useCoAgent,
} from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";
import { createClient } from "@/lib/supabase/client";
import type { User } from "@supabase/supabase-js";
import { StateSelector } from "../components/StateSelector";
import { FileUpload } from "../components/FileUpload";
import { ModeToggle } from "../components/ModeToggle";
import { useMode } from "../contexts/ModeContext";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import Image from "next/image";
import {
  FileCheck,
  X,
  Menu,
  ArrowLeft,
  FileText,
  Home,
  Briefcase,
  Plus,
  Users,
  RefreshCw,
  LogOut,
} from "lucide-react";

export default function ChatPage() {
  const router = useRouter();
  const [userState, setUserState] = useState<string | null>(null);
  const [uploadedDocument, setUploadedDocument] = useState<{
    url: string;
    filename: string;
  } | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  // Fetch current user
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => setUser(user));
  }, []);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  };

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user) return "?";
    const name = user.user_metadata?.full_name || user.email || "";
    if (user.user_metadata?.full_name) {
      return name
        .split(" ")
        .map((n: string) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);
    }
    return (user.email?.[0] || "?").toUpperCase();
  };

  // Get current mode from context
  const { mode } = useMode();

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

  // Share UI mode with the Copilot agent
  useCopilotReadable({
    description: "The UI mode the user has selected",
    value:
      mode === "analysis"
        ? `User is in ANALYSIS MODE. This means they want a thorough consultation like talking to a lawyer. Guide them through understanding their situation first, then explain the relevant law, and finally offer options and strategy when they ask or when it's natural.`
        : `User is in CHAT MODE. This is casual Q&A mode for quick legal questions. Be helpful and conversational.`,
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
  }>({
    name: "auslaw_agent",
  });

  // Quick replies from agent state
  // TODO: Remove mock data after testing - set to undefined to use real backend data
  const quickReplies = agentState?.quick_replies ||
    ["What protections do I have?", "Can you give examples?", "What should I do next?", "How do I file a claim?"];

  // Track if conversation has started (to show/hide welcome section)
  const [conversationStarted, setConversationStarted] = useState(false);

  // Reset conversation handler - reload page to start fresh
  const handleNewConversation = () => {
    window.location.reload();
  };

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
      {/* Mode Toggle */}
      <ModeToggle />

      {/* Divider */}
      <div className="h-px bg-slate-200" />

      {/* Location Section */}
      <div className="space-y-3">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Your Jurisdiction
        </div>
        <StateSelector
          selectedState={userState}
          onStateChange={setUserState}
        />
      </div>

      {/* Document Upload Section */}
      <div className="space-y-3">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Document Analysis
        </div>
        <FileUpload onFileUploaded={handleFileUploaded} />
        {uploadedDocument && (
          <Badge
            variant="secondary"
            className="gap-2 h-10 px-3 bg-emerald-50 text-emerald-700 border border-emerald-200 w-full justify-start text-sm"
          >
            <FileCheck className="h-4 w-4 text-emerald-600 shrink-0" />
            <span className="truncate flex-1 text-left">
              {uploadedDocument.filename}
            </span>
            <button
              onClick={clearDocument}
              className="hover:text-red-600 transition-colors cursor-pointer ml-auto"
              aria-label="Remove document"
            >
              <X className="h-4 w-4" />
            </button>
          </Badge>
        )}
        <p className="text-sm text-slate-500">
          Upload leases, contracts, or legal documents for AI analysis.
        </p>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Generate Brief Button */}
      <GenerateBriefButton onClose={() => setSidebarOpen(false)} />

      {/* New Conversation Button */}
      <Button
        onClick={handleNewConversation}
        variant="outline"
        className="w-full cursor-pointer gap-2 h-10 text-sm font-medium border-slate-200 hover:bg-slate-50 hover:border-slate-300 transition-all"
      >
        <Plus className="h-4 w-4" />
        New Conversation
      </Button>

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
    <div className="flex h-dvh bg-slate-50 chat-page-container">
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
                    <Image src="/logo.svg" alt="AusLaw AI" width={72} height={72} />
                    <span className="font-semibold">AusLaw AI</span>
                  </SheetTitle>
                </SheetHeader>
                <SidebarContent />
              </SheetContent>
            </Sheet>

            <div className="flex items-center gap-2">
              <Image src="/logo.svg" alt="AusLaw AI" width={80} height={80} />
              <span className="font-semibold text-slate-900">AusLaw AI</span>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="cursor-pointer rounded-full h-9 w-9">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-primary/10 text-primary text-xs font-medium">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <p className="text-sm font-medium">{user?.user_metadata?.full_name || "Account"}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="cursor-pointer">
                <Link href="/">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Home
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleSignOut} className="cursor-pointer text-red-600 focus:text-red-600">
                <LogOut className="mr-2 h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-80 xl:w-[340px] flex-col border-r border-slate-200/80 bg-white">
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <Link href="/" className="flex items-center gap-2.5 group">
            <Image src="/logo.svg" alt="AusLaw AI" width={80} height={80} />
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
      <main className="flex-1 flex flex-col min-w-0 bg-gradient-to-b from-slate-50 to-white relative">
        {/* Chat Header */}
        <div className="hidden lg:flex items-center justify-between px-6 py-3 border-b border-slate-200/60 bg-white/80 backdrop-blur-sm">
          <span className="text-sm font-medium text-slate-600">
            {mode === "analysis" ? "Case Analysis" : "Legal Chat"}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="cursor-pointer rounded-full h-9 w-9">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-primary/10 text-primary text-xs font-medium">
                    {getUserInitials()}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <p className="text-sm font-medium">{user?.user_metadata?.full_name || "Account"}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="cursor-pointer">
                <Link href="/">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Home
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleSignOut} className="cursor-pointer text-red-600 focus:text-red-600">
                <LogOut className="mr-2 h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Add top padding on mobile for fixed header */}
        <div className="flex-1 pt-14 lg:pt-0 flex flex-col min-h-0 overflow-hidden">
          {/* Welcome Section - shown only when conversation hasn't started */}
          {!conversationStarted && (
            <WelcomeSection onTopicClick={() => setConversationStarted(true)} />
          )}

          {/* Chat area */}
          <CopilotChat
            className="flex-1 min-h-0"
            labels={{
              title: mode === "analysis" ? "Case Analysis" : "Legal Chat",
              initial: getInitialMessage(),
            }}
          />
        </div>

        {/* Quick Replies - positioned above input, outside overflow container */}
        {quickReplies && quickReplies.length > 0 && (
          <div className="quick-replies-container">
            <QuickRepliesPanel replies={quickReplies} />
          </div>
        )}
      </main>
    </div>
  );
}

/**
 * WelcomeSection - Welcome header with topic pill buttons
 */
function WelcomeSection({ onTopicClick }: { onTopicClick: () => void }) {
  const { appendMessage } = useCopilotChat();

  const topics = [
    {
      icon: Home,
      label: "What are my tenant rights?",
      prompt: "What are my tenant rights?",
    },
    {
      icon: Briefcase,
      label: "Explain unfair dismissal laws",
      prompt: "Explain unfair dismissal laws",
    },
    {
      icon: Users,
      label: "Help with a family law dispute",
      prompt: "Help with a family law dispute",
    },
    {
      icon: RefreshCw,
      label: "What does Australian Consumer Law cover?",
      prompt: "What does Australian Consumer Law cover?",
    },
  ];

  const handleTopicClick = async (prompt: string) => {
    onTopicClick(); // Hide welcome section immediately
    await appendMessage(
      new TextMessage({
        role: MessageRole.User,
        content: prompt,
      })
    );
  };

  return (
    <div className="flex flex-wrap justify-center gap-2 px-4 py-3">
      {topics.map((topic) => (
        <button
          key={topic.label}
          onClick={() => handleTopicClick(topic.prompt)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-full border border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 transition-all duration-200 cursor-pointer group"
        >
          <topic.icon className="h-4 w-4 text-slate-400 group-hover:text-slate-600 transition-colors flex-shrink-0" />
          <span className="text-sm text-slate-600 group-hover:text-slate-900 transition-colors">
            {topic.label}
          </span>
        </button>
      ))}
    </div>
  );
}

/**
 * QuickRepliesPanel - Renders suggested quick reply buttons from agent state
 * Positioned above the input box
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
    <div className="quick-replies-panel">
      {replies.slice(0, 3).map((reply, index) => (
        <Button
          key={index}
          variant="outline"
          size="sm"
          className="text-sm text-slate-600 hover:text-slate-900 hover:bg-white hover:border-primary/30 border-slate-200 bg-white cursor-pointer transition-all rounded-full px-4"
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
      className="w-full bg-primary hover:bg-primary/90 text-white cursor-pointer gap-2 h-10 text-sm font-medium shadow-sm shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
    >
      <FileText className="h-4 w-4" />
      Generate Lawyer Brief
    </Button>
  );
}
