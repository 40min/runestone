import Header from "./components/Header";
import FileUpload from "./components/FileUpload";
import ResultsDisplay from "./components/ResultsDisplay";
import VocabularyView from "./components/VocabularyView";
import GrammarView from "./components/GrammarView";
import useImageProcessing from "./hooks/useImageProcessing";
import { useState } from "react";
import StyledCheckbox from "./components/ui/StyledCheckbox";
import { CustomButton } from "./components/ui"; // Import CustomButton
import { BrainCircuit } from "lucide-react"; // Import BrainCircuit
import { Box } from "@mui/material"; // Import Box for layout

function App() {
  const [currentView, setCurrentView] = useState<
    "analyzer" | "vocabulary" | "grammar"
  >("analyzer");
  const [recognizeOnly, setRecognizeOnly] = useState(false);

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

  return (
    <div className="bg-[#1a102b] min-h-screen">
      <div className="layout-container flex h-full grow flex-col">
        <Header currentView={currentView} onViewChange={setCurrentView} />
        <main className="flex flex-1 justify-center py-12 px-4 sm:px-6 lg:px-8">
          <div className="w-full max-w-4xl space-y-10">
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
            ) : (
              <GrammarView />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
