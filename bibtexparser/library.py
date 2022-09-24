from typing import Collection, Dict, List, Union, ValuesView

from bibtexparser.middleware import BlockMiddleware
from bibtexparser.model import (
    Block,
    DuplicateKeyBlock,
    Entry,
    ExplicitComment,
    ImplicitComment,
    Preamble,
    String, ParsingFailedBlock,
)


# TODO Use functools.lru_cache for library properties (which create lists when called)

class Library:
    def __init__(self, blocks: Union[List[Block], None] = None):
        self._blocks = blocks.copy() if blocks is not None else []
        self._entries_by_key = dict()
        self._strings_by_key = dict()

    def add(self, blocks: Union[List[Block], Block]):
        """Add blocks to library.

        The adding is key-safe, i.e., it is made sure that no duplicate keys are added.
        for the same type (i.e., String or Entry). Duplicates are silently replaced with
        a DuplicateKeyBlock.

        :param blocks: Block or list of blocks to add.
        """
        if isinstance(blocks, Block):
            blocks = [blocks]

        for block in blocks:
            block = self._add_to_dicts(block)
            self._blocks.append(block)

    def remove(self, blocks: Union[List[Block], Block]):
        """Remove blocks from library.

        :param blocks: Block or list of blocks to remove.
        :raises ValueError: If block is not in library."""
        if isinstance(blocks, Block):
            blocks = [blocks]

        for block in blocks:
            self._blocks.remove(block)
            if isinstance(block, Entry):
                del self._entries_by_key[block.key]
            elif isinstance(block, String):
                del self._strings_by_key[block.key]

    def replace(
            self, old_block: Block, new_block: Block, fail_on_duplicate_key: bool = True
    ):
        """Replace a block with another block, at the same position.

        :param old_block: Block to replace.
        :param new_block: Block to replace with.
        :param fail_on_duplicate_key: If False, adds a DuplicateKeyBlock if
                a block with new_block.key (other than old_block) already exists.
        :raises ValueError: If old_block is not in library or if fail_on_duplicate_key is True
                and a block with new_block.key (other than old_block) already exists."""
        try:
            index = self._blocks.index(old_block)
            self.remove(old_block)
        except ValueError:
            raise ValueError("Block to replace is not in library.")

        self._blocks.insert(index, new_block)
        block_after_add = self._add_to_dicts(new_block)

        if (
                new_block is not block_after_add
                and isinstance(new_block, DuplicateKeyBlock)
                and fail_on_duplicate_key
        ):
            # Revert changes to old_block
            #   Don't fail on duplicate key, as this would lead to an infinite recursion
            #   (should never happen for a clean library, but could happen if the user
            #   tampered with the internals of the library).
            self.replace(new_block, old_block, fail_on_duplicate_key=False)
            raise ValueError("Duplicate key found.")

    @staticmethod
    def _cast_to_duplicate(
            prev_block_with_same_key: Union[Entry, String], duplicate: Union[Entry, String]
    ):
        assert isinstance(prev_block_with_same_key, type(duplicate)) or isinstance(
            duplicate, type(prev_block_with_same_key)
        ), (
            "Internal BibtexParser Error. Duplicate blocks share no common type."
            f"Found {type(prev_block_with_same_key)} and {type(duplicate)}, but both should be"
            f"either instance of String or instance of Entry."
            f"Please report this issue at the bibtexparser issue tracker.",
        )

        assert (
                prev_block_with_same_key.key == duplicate.key
        ), "Internal BibtexParser Error. Duplicate blocks have different keys."

        return DuplicateKeyBlock(
            start_line=duplicate.start_line,
            raw=duplicate.raw,
            key=duplicate.key,
            previous_block=prev_block_with_same_key,
            duplicate_block=duplicate,
        )

    def _add_to_dicts(self, block):
        """Safely add block references to private dict structures.

        :param block: Block to add.
        :returns: The block that was added to the library, except if a block
            of same type and with same key already exists, in which case a
            DuplicateKeyBlock is returned.
        """
        if isinstance(block, Entry):
            try:
                prev_block_with_same_key = self._entries_by_key[block.key]
                block = self._cast_to_duplicate(prev_block_with_same_key, block)
            except KeyError:
                pass  # No previous entry with same key
            finally:
                self._entries_by_key[block.key] = block
        elif isinstance(block, String):
            try:
                prev_block_with_same_key = self._strings_by_key[block.key]
                block = self._cast_to_duplicate(prev_block_with_same_key, block)
            except KeyError:
                pass  # No previous string with same key
            finally:
                self._strings_by_key[block.key] = block
        return block

    @property
    def blocks(self) -> List[Block]:
        return self._blocks.copy()

    @property
    def failed_blocks(self) -> List[ParsingFailedBlock]:
        return [b for b in self._blocks if isinstance(b, ParsingFailedBlock)]

    @property
    def strings(self) -> List[String]:
        return list(self._strings_by_key.values())

    @property
    def strings_dict(self) -> Dict[str, String]:
        return self._strings_by_key.copy()

    @property
    def entries(self) -> List[Entry]:
        return list(self._entries_by_key.values())

    @property
    def entries_dict(self) -> Dict[str, Entry]:
        return self._entries_by_key.copy()

    @property
    def preambles(self) -> List[Preamble]:
        return [block for block in self._blocks if isinstance(block, Preamble)]

    @property
    def comments(self) -> List[Union[ExplicitComment, ImplicitComment]]:
        return [
            block
            for block in self._blocks
            if isinstance(block, (ExplicitComment, ImplicitComment))
        ]

    def apply_middleware(
            self, middlewares: Union[BlockMiddleware, Collection[BlockMiddleware]]
    ) -> "Library":
        """Apply a middleware to all blocks in the library.

        :param middlewares: Middleware to apply.
        :returns: A new library with the middleware applied.
        """

        # TODO better implementation, (1) merging middlewares and (2) allowing multithreading
        transformed_blocks = self._blocks.copy()
        if isinstance(middlewares, BlockMiddleware):
            middlewares = [middlewares]
        for block_middleware in middlewares:
            transformed_blocks = [block_middleware.transform(b, self) for b in self._blocks]
        return Library(transformed_blocks)
