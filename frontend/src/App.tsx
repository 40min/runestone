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
import StyledCheckbox from "./components/ui/StyledCheckbox";
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
  const [authView, setAuthView] = useState<AuthView>("login");
  const { isAuthenticated } = useAuth();

  const {
    processImage,
    analyzeText,
    saveVocabulary,
    onVocabularyUpdated,
    ocrResult,
    analysisResult,
    resourcesResult,
    processingStep,
    error,
    isProcessing,
  } = useImageProcessing();

  const handleFileSelect = async (file: File) => {
    await processImage(file, recognizeOnly);
  };

  const handleAnalyzeOcrText = async () => {
    if (ocrResult?.text) {
      await analyzeText(ocrResult.text);
    }
  };

  const isAnalyzeButtonDisabled =
    processingStep === "ANALYZING" || processingStep === "RESOURCES";

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
    <div className="bg-[#1a102b] min-h-screen">
      <div className="layout-container flex h-full grow flex-col">
        <Header currentView={currentView} onViewChange={setCurrentView} />
        <main className="flex flex-1 justify-center py-4 px-2 sm:py-12 sm:px-6 lg:px-8">
          <div
            className={`w-full ${currentView === "chat" ? "max-w-screen-2xl" : "max-w-7xl"} space-y-10`}
          >
            {currentView === "analyzer" ? (
              <>
                <div className="text-center">
                  <h2 className="text-4xl font-bold text-white tracking-tight sm:text-5xl">
                    Analyze Your Swedish Textbook Page
                  </h2>
                  <p className="mt-4 text-lg leading-8 text-gray-300">
                    Upload an image to get an instant analysis of the text,
                    grammar, and vocabulary.
                  </p>
                </div>

                <FileUpload
                  onFileSelect={handleFileSelect}
                  isProcessing={isProcessing}
                />
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <StyledCheckbox
                    label="Recognize only"
                    checked={recognizeOnly}
                    onChange={(checked: boolean) => setRecognizeOnly(checked)}
                  />
                  {recognizeOnly && ocrResult && (
                    <CustomButton
                      onClick={handleAnalyzeOcrText}
                      disabled={isAnalyzeButtonDisabled}
                      sx={{
                        minWidth: 0,
                        padding: "4px 8px",
                        fontSize: "0.75rem",
                      }}
                      aria-label="Analyze"
                    >
                      <BrainCircuit size={16} />
                    </CustomButton>
                  )}
                </Box>

                {(ocrResult ||
                  analysisResult ||
                  resourcesResult ||
                  error ||
                  isProcessing) && (
                  <ResultsDisplay
                    ocrResult={ocrResult}
                    analysisResult={analysisResult}
                    resourcesResult={resourcesResult}
                    error={error}
                    saveVocabulary={saveVocabulary}
                    onVocabularyUpdated={onVocabularyUpdated}
                    processingStep={processingStep}
                    isProcessing={isProcessing}
                  />
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
