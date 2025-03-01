import logging
from dataclasses import dataclass
from typing import Optional

from llama_index.bridge.pydantic import BaseModel

import llama_index
from llama_index.callbacks.base import CallbackManager
from llama_index.embeddings.base import BaseEmbedding
from llama_index.embeddings.utils import EmbedType, resolve_embed_model
from llama_index.indices.prompt_helper import PromptHelper
from llama_index.llm_predictor import LLMPredictor
from llama_index.llm_predictor.base import BaseLLMPredictor, LLMMetadata
from llama_index.llms.base import LLM
from llama_index.llms.utils import LLMType, resolve_llm
from llama_index.logger import LlamaLogger
from llama_index.node_parser.interface import NodeParser
from llama_index.node_parser.sentence_window import SentenceWindowNodeParser
from llama_index.node_parser.simple import SimpleNodeParser
from llama_index.prompts.base import BasePromptTemplate

logger = logging.getLogger(__name__)


def _get_default_node_parser(
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    callback_manager: Optional[CallbackManager] = None,
) -> NodeParser:
    """Get default node parser."""
    return SimpleNodeParser.from_defaults(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        callback_manager=callback_manager,
    )


def _get_default_prompt_helper(
    llm_metadata: LLMMetadata,
    context_window: Optional[int] = None,
    num_output: Optional[int] = None,
) -> PromptHelper:
    """Get default prompt helper."""
    if context_window is not None:
        llm_metadata.context_window = context_window
    if num_output is not None:
        llm_metadata.num_output = num_output
    return PromptHelper.from_llm_metadata(llm_metadata=llm_metadata)


class ServiceContextData(BaseModel):
    llm: dict
    llm_predictor: dict
    prompt_helper: dict
    embed_model: dict
    node_parser: dict
    text_splitter: Optional[dict]
    metadata_extractor: Optional[dict]
    extractors: Optional[list]


@dataclass
class ServiceContext:
    """Service Context container.

    The service context container is a utility container for LlamaIndex
    index and query classes. It contains the following:
    - llm_predictor: BaseLLMPredictor
    - prompt_helper: PromptHelper
    - embed_model: BaseEmbedding
    - node_parser: NodeParser
    - llama_logger: LlamaLogger (deprecated)
    - callback_manager: CallbackManager

    """

    llm_predictor: BaseLLMPredictor
    prompt_helper: PromptHelper
    embed_model: BaseEmbedding
    node_parser: NodeParser
    llama_logger: LlamaLogger
    callback_manager: CallbackManager

    @classmethod
    def from_defaults(
        cls,
        llm_predictor: Optional[BaseLLMPredictor] = None,
        llm: Optional[LLMType] = "default",
        prompt_helper: Optional[PromptHelper] = None,
        embed_model: Optional[EmbedType] = "default",
        node_parser: Optional[NodeParser] = None,
        llama_logger: Optional[LlamaLogger] = None,
        callback_manager: Optional[CallbackManager] = None,
        system_prompt: Optional[str] = None,
        query_wrapper_prompt: Optional[BasePromptTemplate] = None,
        # node parser kwargs
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        # prompt helper kwargs
        context_window: Optional[int] = None,
        num_output: Optional[int] = None,
        # deprecated kwargs
        chunk_size_limit: Optional[int] = None,
    ) -> "ServiceContext":
        """Create a ServiceContext from defaults.
        If an argument is specified, then use the argument value provided for that
        parameter. If an argument is not specified, then use the default value.

        You can change the base defaults by setting llama_index.global_service_context
        to a ServiceContext object with your desired settings.

        Args:
            llm_predictor (Optional[BaseLLMPredictor]): LLMPredictor
            prompt_helper (Optional[PromptHelper]): PromptHelper
            embed_model (Optional[BaseEmbedding]): BaseEmbedding
                or "local" (use local model)
            node_parser (Optional[NodeParser]): NodeParser
            llama_logger (Optional[LlamaLogger]): LlamaLogger (deprecated)
            chunk_size (Optional[int]): chunk_size
            callback_manager (Optional[CallbackManager]): CallbackManager
            system_prompt (Optional[str]): System-wide prompt to be prepended
                to all input prompts, used to guide system "decision making"
            query_wrapper_prompt (Optional[BasePromptTemplate]): A format to wrap
                passed-in input queries.

        Deprecated Args:
            chunk_size_limit (Optional[int]): renamed to chunk_size

        """
        if chunk_size_limit is not None and chunk_size is None:
            logger.warning(
                "chunk_size_limit is deprecated, please specify chunk_size instead"
            )
            chunk_size = chunk_size_limit

        if llama_index.global_service_context is not None:
            return cls.from_service_context(
                llama_index.global_service_context,
                llm_predictor=llm_predictor,
                prompt_helper=prompt_helper,
                embed_model=embed_model,
                node_parser=node_parser,
                llama_logger=llama_logger,
                callback_manager=callback_manager,
                chunk_size=chunk_size,
                chunk_size_limit=chunk_size_limit,
            )

        callback_manager = callback_manager or CallbackManager([])
        if llm != "default":
            if llm_predictor is not None:
                raise ValueError("Cannot specify both llm and llm_predictor")
            llm = resolve_llm(llm)
        llm_predictor = llm_predictor or LLMPredictor(llm=llm)
        if isinstance(llm_predictor, LLMPredictor):
            llm_predictor.llm.callback_manager = callback_manager
            if system_prompt:
                llm_predictor.system_prompt = system_prompt
            if query_wrapper_prompt:
                llm_predictor.query_wrapper_prompt = query_wrapper_prompt

        # NOTE: the embed_model isn't used in all indices
        embed_model = resolve_embed_model(embed_model)
        embed_model.callback_manager = callback_manager

        prompt_helper = prompt_helper or _get_default_prompt_helper(
            llm_metadata=llm_predictor.metadata,
            context_window=context_window,
            num_output=num_output,
        )

        node_parser = node_parser or _get_default_node_parser(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            callback_manager=callback_manager,
        )

        llama_logger = llama_logger or LlamaLogger()

        return cls(
            llm_predictor=llm_predictor,
            embed_model=embed_model,
            prompt_helper=prompt_helper,
            node_parser=node_parser,
            llama_logger=llama_logger,  # deprecated
            callback_manager=callback_manager,
        )

    @classmethod
    def from_service_context(
        cls,
        service_context: "ServiceContext",
        llm_predictor: Optional[BaseLLMPredictor] = None,
        llm: Optional[LLMType] = "default",
        prompt_helper: Optional[PromptHelper] = None,
        embed_model: Optional[EmbedType] = "default",
        node_parser: Optional[NodeParser] = None,
        llama_logger: Optional[LlamaLogger] = None,
        callback_manager: Optional[CallbackManager] = None,
        system_prompt: Optional[str] = None,
        query_wrapper_prompt: Optional[BasePromptTemplate] = None,
        # node parser kwargs
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        # prompt helper kwargs
        context_window: Optional[int] = None,
        num_output: Optional[int] = None,
        # deprecated kwargs
        chunk_size_limit: Optional[int] = None,
    ) -> "ServiceContext":
        """Instantiate a new service context using a previous as the defaults."""
        if chunk_size_limit is not None and chunk_size is None:
            logger.warning(
                "chunk_size_limit is deprecated, please specify chunk_size",
                DeprecationWarning,
            )
            chunk_size = chunk_size_limit

        callback_manager = callback_manager or service_context.callback_manager
        if llm != "default":
            if llm_predictor is not None:
                raise ValueError("Cannot specify both llm and llm_predictor")
            llm = resolve_llm(llm)
            llm_predictor = LLMPredictor(llm=llm)

        llm_predictor = llm_predictor or service_context.llm_predictor
        if isinstance(llm_predictor, LLMPredictor):
            llm_predictor.llm.callback_manager = callback_manager
            if system_prompt:
                llm_predictor.system_prompt = system_prompt
            if query_wrapper_prompt:
                llm_predictor.query_wrapper_prompt = query_wrapper_prompt

        # NOTE: the embed_model isn't used in all indices
        # default to using the embed model passed from the service context
        if embed_model == "default":
            embed_model = service_context.embed_model
        embed_model = resolve_embed_model(embed_model)
        embed_model.callback_manager = callback_manager

        prompt_helper = prompt_helper or _get_default_prompt_helper(
            llm_metadata=llm_predictor.metadata,
            context_window=context_window,
            num_output=num_output,
        )

        node_parser = node_parser or service_context.node_parser
        if chunk_size is not None or chunk_overlap is not None:
            node_parser = _get_default_node_parser(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                callback_manager=callback_manager,
            )

        llama_logger = llama_logger or service_context.llama_logger

        return cls(
            llm_predictor=llm_predictor,
            embed_model=embed_model,
            prompt_helper=prompt_helper,
            node_parser=node_parser,
            llama_logger=llama_logger,  # deprecated
            callback_manager=callback_manager,
        )

    @property
    def llm(self) -> LLM:
        if not isinstance(self.llm_predictor, LLMPredictor):
            raise ValueError("llm_predictor must be an instance of LLMPredictor")
        return self.llm_predictor.llm

    def to_dict(self) -> dict:
        """Convert service context to dict."""
        llm_dict = self.llm_predictor.llm.to_dict()
        llm_predictor_dict = self.llm_predictor.to_dict()

        embed_model_dict = self.embed_model.to_dict()

        prompt_helper_dict = self.prompt_helper.to_dict()

        node_parser_dict = self.node_parser.to_dict()

        metadata_extractor_dict = None
        extractor_dicts = None
        text_splitter_dict = None
        if isinstance(self.node_parser, SimpleNodeParser):
            text_splitter_dict = self.node_parser.text_splitter.to_dict()

        if isinstance(self.node_parser, (SimpleNodeParser, SentenceWindowNodeParser)):
            if self.node_parser.metadata_extractor:
                metadata_extractor_dict = self.node_parser.metadata_extractor.to_dict()
                extractor_dicts = []
                for extractor in self.node_parser.metadata_extractor.extractors:
                    extractor_dicts.append(extractor.to_dict())

        return ServiceContextData(
            llm=llm_dict,
            llm_predictor=llm_predictor_dict,
            prompt_helper=prompt_helper_dict,
            embed_model=embed_model_dict,
            node_parser=node_parser_dict,
            text_splitter=text_splitter_dict,
            metadata_extractor=metadata_extractor_dict,
            extractors=extractor_dicts,
        ).dict()

    @classmethod
    def from_dict(cls, data: dict) -> "ServiceContext":
        from llama_index.embeddings.loading import load_embed_model
        from llama_index.llm_predictor.loading import load_predictor
        from llama_index.llms.loading import load_llm
        from llama_index.node_parser.loading import load_parser
        from llama_index.node_parser.extractors.loading import load_extractor
        from llama_index.text_splitter.loading import load_text_splitter

        service_context_data = ServiceContextData.parse_obj(data)

        llm = load_llm(service_context_data.llm)
        llm_predictor = load_predictor(service_context_data.llm_predictor, llm=llm)

        embed_model = load_embed_model(service_context_data.embed_model)

        prompt_helper = PromptHelper.from_dict(service_context_data.prompt_helper)

        extractors = None
        if service_context_data.extractors:
            extractors = []
            for extractor_dict in service_context_data.extractors:
                extractors.append(load_extractor(extractor_dict, llm=llm))

        metadata_extractor = None
        if service_context_data.metadata_extractor:
            metadata_extractor = load_extractor(
                service_context_data.metadata_extractor,
                extractors=extractors,
            )

        text_splitter = None
        if service_context_data.text_splitter:
            text_splitter = load_text_splitter(service_context_data.text_splitter)

        node_parser = load_parser(
            service_context_data.node_parser,
            text_splitter=text_splitter,
            metadata_extractor=metadata_extractor,
        )

        return cls.from_defaults(
            llm_predictor=llm_predictor,
            prompt_helper=prompt_helper,
            embed_model=embed_model,
            node_parser=node_parser,
        )


def set_global_service_context(service_context: Optional[ServiceContext]) -> None:
    """Helper function to set the global service context."""
    llama_index.global_service_context = service_context
