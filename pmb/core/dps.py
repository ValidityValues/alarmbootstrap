# Copyright 2024 Aster Boese
# SPDX-License-Identifier: GPL-3.0-or-later
# Based on https://uapi-group.org/specifications/specs/discoverable_partitions_specification

boot = {
    "esp": ["ESP", "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"],
    # Not supported by the spec
    "prep": ["PREP", "9e1a2d38-c612-4316-aa26-8b49521e5a8b"],
    "xbootldr": ["XBOOTLDR", "bc13c2ff-59e6-4262-a352-b275fd6f7172"],
}

directory = {
    "swap": ["SD_GPT_SWAP", "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f"],
    "home": ["SD_GPT_HOME", "933ac7e1-2eb4-4f13-b844-0e14e2aef915"],
    "srv": ["SD_GPT_SRV", "3b8f8425-20e0-4f3b-907f-1a25a76f98e8"],
    "var": ["SD_GPT_VAR", "4d21b016-b534-45c2-a9fb-5c16e091fd2d"],
    "tmp": ["SD_GPT_TMP", "7ec6f557-3bc5-4aca-b293-16ef5df639d1"],
    "user_home": ["SD_GPT_USER_HOME", "773f91ef-66d4-49b5-bd83-d683bf40ad16"],
    "generic": ["SD_GPT_LINUX_GENERIC", "0fc63daf-8483-4772-8e79-3d69d8477de4"],
}

root = {
    "x86": ["SD_GPT_ROOT_X86", "44479540-f297-41b2-9af7-d131d5f0458a"],
    "x86_64": ["SD_GPT_ROOT_X86_64", "4f68bce3-e8cd-4db1-96e7-fbcaf984b709"],
    # The three non-x64 ARMs are lumped into ARM
    "armhf": ["SD_GPT_ROOT_ARM", "69dad710-2ce4-4e3c-b16c-21a1d49abed3"],
    "armv7": ["SD_GPT_ROOT_ARM", "69dad710-2ce4-4e3c-b16c-21a1d49abed3"],
    "aarch64": ["SD_GPT_ROOT_ARM64", "b921b045-1df0-41c3-af44-4c6f280d3fae"],
    "riscv64": ["SD_GPT_ROOT_RISCV64", "72ec70a6-cf74-40e6-bd49-4bda08e8f224"],
    "s390x": ["SD_GPT_ROOT_S390X", "5eead9a9-fe09-4a1e-a1d7-520d00531306"],
    "ppc64le": ["SD_GPT_ROOT_PPC64_LE", "c31c45e6-3f39-412e-80fb-4809c4980599"],
    # The three non-x64 ARMs are lumped into ARM
    "armel": ["SD_GPT_ROOT_ARM", "69dad710-2ce4-4e3c-b16c-21a1d49abed3"],
    # Not supported by the spec
    "loongarch32": ["SD_GPT_ROOT_LOONGARCH64", "77055800-792c-4f94-b39a-98c91b762bb6"],
    # Not supported by the spec
    "loongarchx32": ["SD_GPT_ROOT_LOONGARCH64", "77055800-792c-4f94-b39a-98c91b762bb6"],
    "loongarch64": ["SD_GPT_ROOT_LOONGARCH64", "77055800-792c-4f94-b39a-98c91b762bb6"],
    "mips": ["SD_GPT_ROOT_MIPS", "e9434544-6e2c-47cc-bae2-12d6deafb44c"],
    "mips64": ["SD_GPT_ROOT_MIPS64", "d113af76-80ef-41b4-bdb6-0cff4d3d4a25"],
    "mipsel": ["SD_GPT_ROOT_MIPSEL", "37c58c8a-d913-4156-a25f-48b1b64e07f0"],
    "mips64el": ["SD_GPT_ROOT_MIPS64_LE", "700bda43-7a34-4507-b179-eeb93d7a7ca3"],
    "ppc": ["SD_GPT_ROOT_PPC", "1de3f1ef-fa98-47b5-8dcd-4a860a654d78"],
    "ppc64": ["SD_GPT_ROOT_PPC64", "912ade1d-a839-4913-8964-a10eee08fbd2"],
    "riscv32": ["SD_GPT_ROOT_RISCV32", "60d5a7fe-8e7d-435c-b714-3dd8162144e1"],
}

usr = {
    # See above for weirdly named partition types
    "x86": ["SD_GPT_USR_X86", "75250d76-8cc6-458e-bd66-bd47cc81a812"],
    "x86_64": ["SD_GPT_USR_X86_64", "8484680c-9521-48c6-9c11-b0720656f69e"],
    "armhf": ["SD_GPT_USR_ARM", "7386cdf2-203c-47a9-a498-f2ecce45a2d6"],
    "armv7": ["SD_GPT_USR_ARM", "7386cdf2-203c-47a9-a498-f2ecce45a2d6"],
    "aarch64": ["SD_GPT_USR_ARM64", "df3300ce-d69f-4c92-978c-9bfb0f38d820"],
    "riscv64": ["SD_GPT_USR_RISCV64", "b6ed5582-440b-4209-b8da-5ff7c419ea3d"],
    "s390x": ["SD_GPT_USR_S390X", "b325bfbe-c7be-4ab8-8357-139e652d2f6b"],
    "ppc64le": ["SD_GPT_USR_PPC64_LE", "ee2b9983-21e8-4153-86d9-b6901a54d1ce"],
    "armel": ["SD_GPT_USR_ARM", "7386cdf2-203c-47a9-a498-f2ecce45a2d6"],
    "loongarch32": ["SD_GPT_USR_LOONGARCH64", "e611c702-575c-4cbe-9a46-434fa0bf7e3f"],
    "loongarchx32": ["SD_GPT_USR_LOONGARCH64", "e611c702-575c-4cbe-9a46-434fa0bf7e3f"],
    "loongarch64": ["SD_GPT_USR_LOONGARCH64", "e611c702-575c-4cbe-9a46-434fa0bf7e3f"],
    "mips": ["SD_GPT_USR_MIPS", "773b2abc-2a99-4398-8bf5-03baac40d02b"],
    "mips64": ["SD_GPT_USR_MIPS64", "57e13958-7331-4365-8e6e-35eeee17c61b"],
    "mipsel": ["SD_GPT_USR_MIPS_LE", "0f4868e9-9952-4706-979f-3ed3a473e947"],
    "mips64el": ["SD_GPT_USR_MIPS64_LE", "c97c1f32-ba06-40b4-9f22-236061b08aa8"],
    "ppc": ["SD_GPT_USR_PPC", "7d14fec5-cc71-415d-9d6c-06bf0b3c3eaf"],
    "ppc64": ["SD_GPT_USR_PPC64", "2c9739e2-f068-46b3-9fd0-01c5a9afbcca"],
    "riscv32": ["SD_GPT_USR_RISCV32", "b933fb22-5c3f-4f91-af90-e2bb0fa50702"],
}

rootverity = {
    # See above for weirdly named partition types
    "x86": ["SD_GPT_ROOT_X86_VERITY", "d13c5d3b-b5d1-422a-b29f-9454fdc89d76"],
    "x86_64": ["SD_GPT_ROOT_X86_64_VERITY", "2c7357ed-ebd2-46d9-aec1-23d437ec2bf5"],
    "armhf": ["SD_GPT_ROOT_ARM_VERITY", "7386cdf2-203c-47a9-a498-f2ecce45a2d6"],
    "armv7": ["SD_GPT_ROOT_ARM_VERITY", "7386cdf2-203c-47a9-a498-f2ecce45a2d6"],
    "aarch64": ["SD_GPT_ROOT_ARM64_VERITY", "df3300ce-d69f-4c92-978c-9bfb0f38d820"],
    "riscv64": ["SD_GPT_ROOT_RISCV64_VERITY", "b6ed5582-440b-4209-b8da-5ff7c419ea3d"],
    "s390x": ["SD_GPT_ROOT_S390X_VERITY", "b325bfbe-c7be-4ab8-8357-139e652d2f6b"],
    "ppc64le": ["SD_GPT_ROOT_PPC64_LE_VERITY", "906bd944-4589-4aae-a4e4-dd983917446a"],
    "armel": ["SD_GPT_ROOT_ARM_VERITY", "7386cdf2-203c-47a9-a498-f2ecce45a2d6"],
    "loongarch32": [
        "SD_GPT_ROOT_LOONGARCH64_VERITY",
        "f3393b22-e9af-4613-a948-9d3bfbd0c535",
    ],
    "loongarchx32": [
        "SD_GPT_ROOT_LOONGARCH64_VERITY",
        "f3393b22-e9af-4613-a948-9d3bfbd0c535",
    ],
    "loongarch64": [
        "SD_GPT_ROOT_LOONGARCH64_VERITY",
        "f3393b22-e9af-4613-a948-9d3bfbd0c535",
    ],
    "mips": ["SD_GPT_ROOT_MIPS_VERITY", "7a430799-f711-4c7e-8e5b-1d685bd48607"],
    "mips64": ["SD_GPT_ROOT_MIPS64_VERITY", "579536f8-6a33-4055-a95a-df2d5e2c42a8"],
    "mipsel": ["SD_GPT_ROOT_MIPS_LE_VERITY", "d7d150d2-2a04-4a33-8f12-16651205ff7b"],
    "mips64el": ["SD_GPT_ROOT_MIPS64_LE_VERITY", "16b417f8-3e06-4f57-8dd2-9b5232f41aa6"],
    "ppc": ["SD_GPT_ROOT_PPC_VERITY", "98cfe649-1588-46dc-b2f0-add147424925"],
    "ppc64": ["SD_GPT_ROOT_PPC64_VERITY", "9225a9a3-3c19-4d89-b4f6-eeff88f17631"],
    "riscv32": ["SD_GPT_ROOT_RISCV32_VERITY", "ae0253be-1167-4007-ac68-43926c14c5de"],
}

usrverity = {
    # See above for weirdly named partition types
    "x86": ["SD_GPT_USR_X86_VERITY", "8f461b0d-14ee-4e81-9aa9-049b6fb97abd"],
    "x86_64": ["SD_GPT_USR_X86_64_VERITY", "77ff5f63-e7b6-4633-acf4-1565b864c0e6"],
    "armhf": ["SD_GPT_USR_ARM_VERITY", "c215d751-7bcd-4649-be90-6627490a4c05"],
    "armv7": ["SD_GPT_USR_ARM_VERITY", "c215d751-7bcd-4649-be90-6627490a4c05"],
    "arm64": ["SD_GPT_USR_ARM64_VERITY", "6e11a4e7-fbca-4ded-b9e9-e1a512bb664e"],
    "riscv64": ["SD_GPT_USR_RISCV64_VERITY", "8f1056be-9b05-47c4-81d6-be53128e5b54"],
    "s390x": ["SD_GPT_USR_S390X_VERITY", "31741cc4-1a2a-4111-a581-e00b447d2d06"],
    "ppc64le": ["SD_GPT_USR_PPC64_LE_VERITY", "ee2b9983-21e8-4153-86d9-b6901a54d1ce"],
    "armel": ["SD_GPT_USR_ARM_VERITY", "c215d751-7bcd-4649-be90-6627490a4c05"],
    "loongarch32": [
        "SD_GPT_USR_LOONGARCH64_VERITY",
        "f46b2c26-59ae-48f0-9106-c50ed47f673d",
    ],
    "loongarchx32": [
        "SD_GPT_USR_LOONGARCH64_VERITY",
        "f46b2c26-59ae-48f0-9106-c50ed47f673d",
    ],
    "loongarch64": [
        "SD_GPT_USR_LOONGARCH64_VERITY",
        "f46b2c26-59ae-48f0-9106-c50ed47f673d",
    ],
    "mips": ["SD_GPT_USR_MIPS_VERITY", "6e5a1bc8-d223-49b7-bca8-37a5fcceb996"],
    "mips64": ["SD_GPT_USR_MIPS64_VERITY", "81cf9d90-7458-4df4-8dcf-c8a3a404f09b"],
    "mipsel": ["SD_GPT_USR_MIPS_LE_VERITY", "46b98d8d-b55c-4e8f-aab3-37fca7f80752"],
    "mips64el": ["SD_GPT_USR_MIPS64_LE_VERITY", "3c3d61fe-b5f3-414d-bb71-8739a694a4ef"],
    "ppc": ["SD_GPT_USR_PPC_VERITY", "df765d00-270e-49e5-bc75-f47bb2118b09"],
    "ppc64": ["SD_GPT_USR_PPC64_VERITY", "bdb528a5-a259-475f-a87d-da53fa736a07"],
    "riscv32": ["SD_GPT_USR_RISCV32_VERITY", "cb1ee4e3-8cd0-4136-a0a4-aa61a32e8730"],
}
