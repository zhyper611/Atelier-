type KnowledgeModeToggleProps = {
  useKnowledgeBase: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
};

export function KnowledgeModeToggle({
  useKnowledgeBase,
  onChange,
  disabled,
}: KnowledgeModeToggleProps) {
  return (
    <div className="knowledge-mode-toggle" role="group" aria-label="检索模式">
      <span className="knowledge-mode-toggle__label">检索</span>
      <button
        type="button"
        className={`knowledge-mode-toggle__option${
          useKnowledgeBase ? " knowledge-mode-toggle__option--active" : ""
        }`}
        onClick={() => onChange(true)}
        disabled={disabled}
        aria-pressed={useKnowledgeBase}
        title="仅依据已上传知识库文档作答，不联网"
      >
        知识库
      </button>
      <button
        type="button"
        className={`knowledge-mode-toggle__option${
          !useKnowledgeBase ? " knowledge-mode-toggle__option--active" : ""
        }`}
        onClick={() => onChange(false)}
        disabled={disabled}
        aria-pressed={!useKnowledgeBase}
        title="联网搜索实时信息，不检索知识库"
      >
        联网
      </button>
      <span className="knowledge-mode-toggle__hint">
        {useKnowledgeBase
          ? "按已上传文档检索作答"
          : "搜索新闻、天气等实时信息"}
      </span>
    </div>
  );
}
