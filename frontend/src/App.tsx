import Header from "./components/Header";
import FileUpload from "./components/FileUpload";
import ResultsDisplay from "./components/ResultsDisplay";
import VocabularyView from "./components/VocabularyView";
import GrammarView from "./components/GrammarView";
import ChatView from "./components/ChatView";
import Login from "./components/auth/Login";
import Register from "./components/auth/Register";
import Profile from "./components/auth/Profile";
import useImageProcessing from "./hooks/useImageProcessing";
import { useState, useEffect } from "react";
import { CustomButton } from "./components/ui";
import { BrainCircuit } from "lucide-react";
import { Box } from "@mui/material";
import { useAuth } from "./context/AuthContext";

type AuthView = "login" | "register";
type ViewType = "analyzer" | "vocabulary" | "grammar" | "chat" | "profile";

const VIEW_NAMES: Record<ViewType, string> = {
  analyzer: "Analyzer",
  vocabulary: "Vocabulary",
  grammar: "Grammar",
  chat: "Chat",
  profile: "Profile",
};

const STORAGE_KEY = "runestone_current_view";
const VALID_VIEWS: ViewType[] = ["analyzer", "vocabulary", "grammar", "chat", "profile"];

function getInitialView(): ViewType {
  if (typeof window === "undefined") return "analyzer";

  const params = new URLSearchParams(window.location.search);
  const viewFromUrl = params.get("view");
  if (viewFromUrl && VALID_VIEWS.includes(viewFromUrl as ViewType)) {
    return viewFromUrl as ViewType;
  }

  const stored = localStorage.getItem(STORAGE_KEY);
  return stored && VALID_VIEWS.includes(stored as ViewType)
    ? (stored as ViewType)
    : "analyzer";
}

function App() {
  const [currentView, setCurrentView] = useState<ViewType>(getInitialView);
  const [recognizeOnly, setRecognizeOnly] = useState(false);
  const [lastSelectedFile, setLastSelectedFile] = useState<File | null>(null);
  const [authView, setAuthView] = useState<AuthView>("login");
  const { isAuthenticated } = useAuth();

  const {
    processImage,
    analyzeText,
    saveVocabulary,
    onVocabularyUpdated,
    ocrResult,
    analysisResult,
    processingStep,
    error,
    isProcessing,
  } = useImageProcessing();

  const handleFileSelect = async (file: File) => {
    setLastSelectedFile(file);
    await processImage(file, recognizeOnly);
  };

  const handleAnalyzeOcrText = async () => {
    if (ocrResult?.text) {
      await analyzeText(ocrResult.text);
    }
  };

  const isAnalyzeButtonDisabled =
    processingStep === "ANALYZING";
  const hasAnalyzerContent = Boolean(
    ocrResult || analysisResult || error || isProcessing
  );

  // Persist view changes to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, currentView);
  }, [currentView]);

  // Sync view to URL for shareable deep-links (e.g. ?view=grammar&cheatsheet=verbs/imperativ.md)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.set("view", currentView);
    if (currentView !== "grammar") {
      url.searchParams.delete("cheatsheet");
    }
    window.history.replaceState({}, "", url);
  }, [currentView]);

  // Update title based on current view
  useEffect(() => {
    document.title = `Runestone | ${VIEW_NAMES[currentView]}`;
  }, [currentView]);

  // Update title for auth views
  useEffect(() => {
    if (!isAuthenticated()) {
      document.title = `Runestone | ${authView === "register" ? "Register" : "Login"}`;
    }
  }, [authView, isAuthenticated]);

  // If not authenticated, show auth views
  if (!isAuthenticated()) {
    if (authView === "register") {
      return <Register onSwitchToLogin={() => setAuthView("login")} />;
    }
    return <Login onSwitchToRegister={() => setAuthView("register")} />;
  }

  return (
    <div className="min-h-screen bg-[#060b26]">
      <div className="layout-container flex h-full grow flex-col">
        <Header currentView={currentView} onViewChange={setCurrentView} />
        <main className={`flex flex-1 justify-center ${currentView === "chat" ? "" : "py-4 px-2 sm:py-12 sm:px-6 lg:px-8"}`}>
          <div
            className={`w-full ${currentView === "chat" ? "max-w-screen-2xl h-full" : "max-w-7xl space-y-10"}`}
          >
            {currentView === "analyzer" ? (
              <>
                <div className="space-y-3 text-left">
                  <h2 className="text-4xl font-bold tracking-tight text-slate-100 sm:text-5xl">
                    Analyze Your Swedish Textbook Page
                  </h2>
                  <p className="max-w-3xl text-lg leading-8 text-slate-300">
                    Upload an image to get an instant analysis of the text,
                    grammar, and vocabulary.
                  </p>
                </div>

                {!hasAnalyzerContent ? (
                  <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
                    <FileUpload
                      onFileSelect={handleFileSelect}
                      isProcessing={isProcessing}
                      recognizeOnly={recognizeOnly}
                      onRecognizeOnlyChange={setRecognizeOnly}
                      selectedFileOverride={lastSelectedFile}
                    />
                    <Box
                      sx={{
                        display: { xs: "none", lg: "flex" },
                        minHeight: "420px",
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: "0.75rem",
                        border: "1px solid rgba(99, 114, 173, 0.35)",
                        background:
                          "radial-gradient(circle at 20% 20%, rgba(32, 40, 95, 0.55), rgba(8, 11, 39, 0.94))",
                        color: "#c2cee8",
                        textAlign: "center",
                        px: 4,
                      }}
                    >
                      <div className="space-y-4">
                        <div className="text-4xl text-slate-500">⌁</div>
                        <h3 className="text-4xl font-semibold text-slate-100">
                          No analysis yet
                        </h3>
                        <p className="max-w-md text-lg text-slate-300">
                          Upload an image of a Swedish textbook page to get
                          started.
                        </p>
                      </div>
                    </Box>
                  </div>
                ) : (
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
                    <div className="lg:w-[300px] lg:shrink-0">
                      <FileUpload
                        onFileSelect={handleFileSelect}
                        isProcessing={isProcessing}
                        recognizeOnly={recognizeOnly}
                        onRecognizeOnlyChange={setRecognizeOnly}
                        selectedFileOverride={lastSelectedFile}
                        compact
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      {recognizeOnly && ocrResult && !analysisResult && (
                        <Box sx={{ mb: 2 }}>
                          <CustomButton
                            onClick={handleAnalyzeOcrText}
                            disabled={isAnalyzeButtonDisabled}
                            startIcon={<BrainCircuit size={16} />}
                          >
                            Analyze OCR Text
                          </CustomButton>
                        </Box>
                      )}
                      <ResultsDisplay
                        ocrResult={ocrResult}
                        analysisResult={analysisResult}
                        error={error}
                        saveVocabulary={saveVocabulary}
                        onVocabularyUpdated={onVocabularyUpdated}
                        processingStep={processingStep}
                        isProcessing={isProcessing}
                      />
                    </div>
                  </div>
                )}
              </>
            ) : currentView === "vocabulary" ? (
              <VocabularyView />
            ) : currentView === "grammar" ? (
              <GrammarView />
            ) : currentView === "chat" ? (
              <ChatView />
            ) : (
              <Profile />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
