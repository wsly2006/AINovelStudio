<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import CharacterStateEvents from './CharacterStateEvents.vue'

const props = defineProps({
  character: { type: Object, default: null },
  // 工程的阶梯列表(供绑定)
  ladders: { type: Array, default: () => [] },
  // 工程的地点(world entities kind=location)
  locations: { type: Array, default: () => [] },
  // 状态事件 UI 需要:工程章节、世界观全集、工程 id
  chapters: { type: Array, default: () => [] },
  worldEntities: { type: Array, default: () => [] },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['save'])

const { t } = useI18n()

const ROLE_OPTIONS = [
  { value: '主角', labelKey: 'cardRoleMain' },
  { value: '配角', labelKey: 'cardRoleSupport' },
  { value: '反派', labelKey: 'cardRoleVillain' },
  { value: '路人', labelKey: 'cardRoleMinor' },
]

const form = ref(emptyForm())
const saving = ref(false)

const showProgressionFields = computed(() => props.ladders.length > 0)

const currentLadder = computed(() =>
  props.ladders.find((l) => l.id === form.value.ladder_id) || null
)
const tierOptions = computed(() => currentLadder.value?.tiers || [])

function emptyForm() {
  return {
    name: '',
    aliases: [],
    role: '',
    profile: '',
    appearance: '',
    personality: '',
    background: '',
    ladder_id: null,
    current_tier_index: null,
    current_location_id: null,
  }
}

watch(
  () => props.character,
  (c) => {
    if (c) {
      form.value = {
        name: c.name || '',
        aliases: [...(c.aliases || [])],
        role: c.role || '',
        profile: c.profile || '',
        appearance: c.appearance || '',
        personality: c.personality || '',
        background: c.background || '',
        ladder_id: c.ladder_id ?? null,
        current_tier_index: c.current_tier_index ?? null,
        current_location_id: c.current_location_id ?? null,
      }
    } else {
      form.value = emptyForm()
    }
  },
  { immediate: true }
)

// 切换 ladder 时,若当前 tier 越界,清空
watch(
  () => form.value.ladder_id,
  (newId, oldId) => {
    if (newId !== oldId) {
      form.value.current_tier_index = null
    }
  }
)

async function onSave() {
  if (!form.value.name.trim()) return
  saving.value = true
  try {
    await emit('save', { ...form.value })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="char-editor">
    <el-form label-position="top" class="form">
      <el-form-item :label="t('characters.fieldName')" required>
        <el-input
          v-model="form.name"
          :placeholder="t('characters.fieldNamePlaceholder')"
          maxlength="120"
          show-word-limit
        />
      </el-form-item>

      <el-form-item :label="t('characters.fieldAliases')">
        <el-select
          v-model="form.aliases"
          multiple
          filterable
          allow-create
          default-first-option
          :placeholder="t('characters.fieldAliasesPlaceholder')"
          style="width: 100%"
          tag-type="info"
        >
          <el-option v-for="a in form.aliases" :key="a" :label="a" :value="a" />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('characters.fieldRole')">
        <el-select
          v-model="form.role"
          :placeholder="t('characters.fieldRolePlaceholder')"
          clearable
          style="width: 240px"
        >
          <el-option
            v-for="opt in ROLE_OPTIONS"
            :key="opt.value"
            :value="opt.value"
            :label="t(`characters.${opt.labelKey}`)"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('characters.fieldProfile')">
        <el-input
          v-model="form.profile"
          type="textarea"
          :rows="2"
          :placeholder="t('characters.fieldProfilePlaceholder')"
        />
      </el-form-item>

      <div class="grid">
        <el-form-item :label="t('characters.fieldAppearance')">
          <el-input v-model="form.appearance" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item :label="t('characters.fieldPersonality')">
          <el-input v-model="form.personality" type="textarea" :rows="4" />
        </el-form-item>
      </div>

      <el-form-item :label="t('characters.fieldBackground')">
        <el-input v-model="form.background" type="textarea" :rows="5" />
      </el-form-item>

      <!-- 进阶字段:工程内有阶梯时才显示 -->
      <div v-if="showProgressionFields" class="progression-block">
        <div class="grid">
          <el-form-item :label="t('characters.fieldLadder')">
            <el-select
              v-model="form.ladder_id"
              :placeholder="t('characters.fieldLadderPlaceholder')"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="l in ladders"
                :key="l.id"
                :value="l.id"
                :label="l.name"
              />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('characters.fieldTier')">
            <el-select
              v-model="form.current_tier_index"
              :placeholder="t('characters.fieldTierPlaceholder')"
              :disabled="!form.ladder_id || tierOptions.length === 0"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="(tier, idx) in tierOptions"
                :key="idx"
                :value="idx"
                :label="`${idx + 1}. ${tier}`"
              />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item :label="t('characters.fieldLocation')">
          <el-select
            v-model="form.current_location_id"
            :placeholder="t('characters.fieldLocationPlaceholder')"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="loc in locations"
              :key="loc.id"
              :value="loc.id"
              :label="loc.name"
            />
          </el-select>
        </el-form-item>
      </div>
    </el-form>

    <div class="actions">
      <el-button type="primary" :loading="saving" :disabled="!form.name.trim()" @click="onSave">
        {{ t('common.save') }}
      </el-button>
    </div>

    <!-- 状态事件:仅对已保存的人物显示 -->
    <CharacterStateEvents
      v-if="character?.id && projectId"
      :character-id="character.id"
      :project-id="projectId"
      :chapters="chapters"
      :ladders="ladders"
      :ladder-id="form.ladder_id"
      :world-entities="worldEntities"
    />
  </div>
</template>

<style scoped>
.char-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  overflow: auto;
}
.form {
  flex: 1;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.progression-block {
  border-top: 1px dashed #e5e6eb;
  padding-top: 12px;
  margin-top: 4px;
}
.actions {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  background: #fff;
  border-top: 1px solid #f2f3f5;
}
</style>
