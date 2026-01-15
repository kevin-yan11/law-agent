"use client";

import { useState } from "react";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { useCopilotReadable } from "@copilotkit/react-core";
import { StateSelector } from "./components/StateSelector";
import { FileUpload } from "./components/FileUpload";

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
    <div className="flex h-screen bg-slate-50">
      {/* Left Side: Info Panel */}
      <div className="w-1/2 p-8 border-r border-slate-200 flex flex-col">
        {/* Header with State Selector */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-800">AusLaw AI</h1>
          <StateSelector selectedState={userState} onStateChange={setUserState} />
        </div>

        {/* Info Cards */}
        <div className="space-y-4 flex-1">
          {/* Current State Info */}
          {userState && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-blue-800">
                <span className="text-lg">📍</span>
                <span className="font-medium">Your jurisdiction: {userState}</span>
              </div>
              <p className="text-blue-600 text-sm mt-1">
                Legal information will be tailored to {userState} law.
              </p>
            </div>
          )}

          {/* Document Upload */}
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h3 className="font-medium text-slate-800 mb-3">Upload Document</h3>
            <p className="text-slate-600 text-sm mb-3">
              Upload a lease, contract, or legal document for analysis.
            </p>
            <FileUpload onFileUploaded={handleFileUploaded} />
            {uploadedDocument && (
              <div className="mt-3 p-2 bg-green-50 border border-green-200 rounded flex items-center justify-between">
                <span className="text-green-700 text-sm truncate">
                  {uploadedDocument.filename} ready for analysis
                </span>
                <button
                  onClick={clearDocument}
                  className="text-green-600 hover:text-green-800 text-sm ml-2"
                >
                  Clear
                </button>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="bg-white border border-slate-200 rounded-lg p-4">
            <h3 className="font-medium text-slate-800 mb-3">Common Questions</h3>
            <div className="space-y-2">
              <QuickAction text="What are my rights as a tenant?" />
              <QuickAction text="How do I get my bond back?" />
              <QuickAction text="Can my landlord increase rent?" />
              <QuickAction text="I need a lawyer" />
            </div>
          </div>

          {/* Disclaimer */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mt-auto">
            <p className="text-amber-800 text-sm">
              <strong>Disclaimer:</strong> This tool provides general legal information,
              not legal advice. For advice specific to your situation, please consult
              a qualified lawyer.
            </p>
          </div>
        </div>
      </div>

      {/* Right Side: Copilot Sidebar */}
      <div className="w-1/2 relative">
        <CopilotSidebar
          defaultOpen={true}
          labels={{
            title: "AusLaw AI",
            initial: getInitialMessage(),
          }}
          imageUploadsEnabled={true}
          inputFileAccept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
        />
      </div>
    </div>
  );
}

function QuickAction({ text }: { text: string }) {
  return (
    <button className="w-full text-left px-3 py-2 text-sm text-slate-600 bg-slate-50 hover:bg-slate-100 rounded-md transition">
      → {text}
    </button>
  );
}
