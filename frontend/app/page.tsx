"use client";

import { useState } from "react";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCopilotReadable, useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";
import { StateSelector } from "./components/StateSelector";
import { FileUpload } from "./components/FileUpload";
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
  Scale,
  MapPin,
  AlertTriangle,
  ArrowRight,
  FileCheck,
  X,
} from "lucide-react";

export default function Home() {
  const [userState, setUserState] = useState<string | null>(null);
  const [uploadedDocument, setUploadedDocument] = useState<{
    url: string;
    filename: string;
  } | null>(null);

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

  // Dynamic initial message based on selected state
  const getInitialMessage = () => {
    if (userState) {
      return `G'day! I'm AusLaw AI, your Australian legal assistant. I see you're in ${userState}. I can help you with:\n\n• Understanding your legal rights\n• Step-by-step guides for legal procedures\n• Finding a lawyer\n\nWhat would you like to know?`;
    }
    return "G'day! I'm AusLaw AI, your Australian legal assistant. Please select your state above so I can provide accurate information for your jurisdiction.";
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Left Side: Info Panel */}
      <div className="w-1/2 p-10 border-r border-slate-200/80 flex flex-col overflow-y-auto">
        {/* Header with State Selector */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Scale className="h-7 w-7 text-blue-600" />
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              AusLaw AI
            </h1>
          </div>
          <StateSelector selectedState={userState} onStateChange={setUserState} />
        </div>

        {/* Info Cards */}
        <div className="space-y-5 flex-1">
          {/* Current State Info */}
          {userState && (
            <Alert className="border-blue-200 bg-blue-50/80">
              <MapPin className="h-4 w-4 text-blue-600" />
              <AlertTitle className="text-blue-800">
                Your jurisdiction: {userState}
              </AlertTitle>
              <AlertDescription className="text-blue-600">
                Legal information will be tailored to {userState} law.
              </AlertDescription>
            </Alert>
          )}

          {/* Document Upload */}
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium">
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
                  <Badge variant="secondary" className="gap-2 py-1.5">
                    <FileCheck className="h-3 w-3 text-green-600" />
                    <span className="truncate max-w-[180px]">
                      {uploadedDocument.filename}
                    </span>
                    <button
                      onClick={clearDocument}
                      className="ml-1 hover:text-destructive transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Ready for analysis
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-medium">
                Common Questions
              </CardTitle>
              <CardDescription>Click to ask a question in the chat.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              <QuickAction text="What are my rights as a tenant?" />
              <QuickAction text="How do I get my bond back?" />
              <QuickAction text="Can my landlord increase rent?" />
              <QuickAction text="I need a lawyer" />
            </CardContent>
          </Card>

          {/* Disclaimer */}
          <Alert className="mt-auto border-amber-200 bg-amber-50/80">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertTitle className="text-amber-800">Disclaimer</AlertTitle>
            <AlertDescription className="text-amber-700">
              This tool provides general legal information, not legal advice. For
              advice specific to your situation, please consult a qualified lawyer.
            </AlertDescription>
          </Alert>
        </div>
      </div>

      {/* Right Side: Copilot Chat */}
      <div className="w-1/2 flex flex-col">
        <CopilotChat
          className="h-full"
          labels={{
            title: "AusLaw AI",
            initial: getInitialMessage(),
          }}
        />
      </div>
    </div>
  );
}

function QuickAction({ text }: { text: string }) {
  const { appendMessage } = useCopilotChat();

  const handleClick = async () => {
    await appendMessage(
      new TextMessage({
        role: MessageRole.User,
        content: text,
      })
    );
  };

  return (
    <Button
      variant="ghost"
      className="w-full justify-start text-left h-auto py-2.5 px-3 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100"
      onClick={handleClick}
    >
      <ArrowRight className="mr-2 h-3 w-3 text-slate-400" />
      {text}
    </Button>
  );
}
